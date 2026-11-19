import ast
import json
from pathlib import Path
import tempfile
import unittest
from harness.ast_guard import safe_path,validate_edit
from harness.engine import Engine,copy_workspace
from harness.intelligence import inspect_python_repo
from harness.llm.client import DemoModel
from harness.sandbox.runner import test_command,run_tests
from harness.cli import DEMO_REPO


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'module.py').write_text('def keep():\n    return 1\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_reject_path_traversal(self):
        for path in ('../x.py','/tmp/x.py','.env','folder/../../x.py','folder/.secret.py'):
            with self.subTest(path=path),self.assertRaises(ValueError):
                safe_path(self.root,path)

    def test_reject_symlinks(self):
        (self.root/'link.py').symlink_to(self.root/'module.py')
        with self.assertRaises(ValueError):
            safe_path(self.root,'link.py')

    def test_reject_removed_definitions(self):
        with self.assertRaisesRegex(ValueError,'removed'):
            validate_edit(self.root,'module.py','print(2)\n',scope={'module.py'})

    def test_reject_dynamic_execution(self):
        with self.assertRaisesRegex(ValueError,'dynamic'):
            validate_edit(self.root,'module.py','def keep():\n    eval("1")\n')

    def test_reject_unauthorized_scope(self):
        with self.assertRaisesRegex(ValueError,'scope'):
            validate_edit(self.root,'module.py','def keep():\n    return 2\n',scope={'else.py'})

    def test_accept_simple_patch(self):
        validate_edit(self.root,'module.py','def keep():\n    return 2\n',scope={'module.py'})

    def test_ast_index(self):
        data = inspect_python_repo(self.root)
        self.assertIn('keep',data['module.py']['functions'])

    def test_test_command_rejects_shell(self):
        with self.assertRaises(ValueError):
            test_command('sh -c rm -rf /')
        with self.assertRaises(ValueError):
            test_command('python -m unittest; touch x')


class EngineTests(unittest.TestCase):
    def test_local_opt_in_required(self):
        with self.assertRaises(RuntimeError):
            run_tests(DEMO_REPO,'python -m unittest discover -s tests',sandbox='local')

    def test_mock_self_healing_and_no_source_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/'results'
            original = (DEMO_REPO/'calculator.py').read_text()
            engine = Engine(DemoModel(),task='Fix calculator.add',
                test_command='python -m unittest discover -s tests -v',
                sandbox='local',allow_unsafe_local=True,max_retries=1)
            result = engine.run(DEMO_REPO,out)
            self.assertTrue(result.success,result.error)
            self.assertEqual(result.attempts,2)
            self.assertEqual(result.changed_files,['calculator.py'])
            self.assertIn('return a + b',result.patch.read_text())
            self.assertEqual((DEMO_REPO/'calculator.py').read_text(),original)
            events = [json.loads(x)['agent'] for x in result.trace.read_text().splitlines()]
            for agent in ('planner','coder','reviewer','security','tester','debugger'):
                self.assertIn(agent,events)

    def test_exhausted_retries(self):
        with tempfile.TemporaryDirectory() as d:
            engine = Engine(DemoModel(),task='Fix calculator.add',
                test_command='python -m unittest discover -s tests',
                sandbox='local',allow_unsafe_local=True,max_retries=0)
            result = engine.run(DEMO_REPO,Path(d)/'out')
            self.assertFalse(result.success)
            self.assertEqual(result.attempts,1)


if __name__=='__main__':
    unittest.main()
