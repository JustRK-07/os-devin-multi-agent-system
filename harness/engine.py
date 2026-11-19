"""Multi-role coding workflow with bounded repair, approval gates and patch output.

The native runner requires no third-party packages. An optional LangGraph adapter
uses the same agent nodes and conditional routing when installed.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from harness.ast_guard import safe_path, validate_edit
from harness.events.trace import Trace
from harness.intelligence import inspect_python_repo
from harness.sandbox.runner import run_tests

IGNORE = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
          '.env', '.DS_Store', 'dist', 'build', 'results', '.mypy_cache'}


class WorkflowState(TypedDict, total=False):
    plan: list[str]
    scope: list[str]
    edits: list[dict]
    attempts: int
    error: str
    passed: bool
    stage_ok: bool
    tests_output: str
    changed: list[str]


@dataclass
class RunResult:
    success: bool
    attempts: int
    changed_files: list[str]
    error: str
    patch: Path
    trace: Path
    report: Path
    workflow: str


def snapshot(root: Path, allowed: set[str] | None = None) -> str:
    files: list[str] = []
    total = 0
    for file in sorted(root.rglob('*')):
        if not file.is_file() or file.is_symlink() or any(p in IGNORE or p.startswith('.') for p in file.relative_to(root).parts):
            continue
        rel = file.relative_to(root).as_posix()
        if allowed is not None and rel not in allowed:
            continue
        if file.suffix not in ('.py','.js','.ts','.tsx','.jsx','.json','.txt','.md','.yaml','.yml'):
            continue
        if file.stat().st_size > 24_000 or total + file.stat().st_size > 65_000:
            continue
        content = file.read_text(encoding='utf-8',errors='replace')
        files.append(f'### {rel}\n{content}\n')
        total += len(content)
        if len(files) >= 35:
            break
    return '\n'.join(files)


def copy_workspace(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        raise ValueError('source and workspace must differ')
    if not source.is_dir():
        raise ValueError('source repository directory does not exist')
    def ignore(directory, names):
        return {name for name in names if name in IGNORE or name.startswith('.') or
                (Path(directory,name).is_symlink()) or
                (Path(directory,name).is_file() and Path(directory,name).stat().st_size > 512_000)}
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)


class Engine:
    def __init__(self, model, *, task: str, test_command: str, sandbox='docker',
                 allow_unsafe_local=False, max_retries=2, graph='native'):
        if not 0 <= max_retries <= 5:
            raise ValueError('max_retries must be between 0 and 5')
        if graph not in ('native','langgraph'):
            raise ValueError('graph must be native or langgraph')
        self.model, self.task, self.test_command = model, task, test_command
        self.sandbox, self.allow_unsafe_local = sandbox, allow_unsafe_local
        self.max_retries, self.graph = max_retries, graph

    def record(self, role: str, event: str, **info) -> None:
        self.trace.record(role, event, **info)

    def planner(self, state: WorkflowState) -> dict:
        context = {'task': self.task, 'repository': snapshot(self.workspace),
                   'ast_index': inspect_python_repo(self.workspace)}
        response = self.model.complete('planner',
            'Return JSON {"plan":["step"],"files":["relative_file.py"]}. '
            'Plan only minimal edits. Repository context:\n' + json.dumps(context))
        scope = response.get('files', [])
        if not isinstance(scope,list) or not scope or len(scope) > 12:
            raise ValueError('planner returned invalid file scope')
        for path in scope:
            safe_path(self.workspace, path)
        plan = response.get('plan', [])
        if not isinstance(plan,list):
            raise ValueError('invalid plan')
        self.record('planner','planned',scope=scope,steps=len(plan))
        return {'plan':plan, 'scope':scope,'attempts':0, 'changed':[]}

    def coder(self, state: WorkflowState) -> dict:
        prompt = ('Return JSON {"edits":[{"path":"...","content":"full UTF-8 file"}]}. '
                  'Implement task, change only allowed files, no markdown fences. '\
                  + json.dumps({'task':self.task,'plan':state['plan'],'scope':state['scope'],
                                'files':snapshot(self.workspace,set(state['scope']))}))
        response = self.model.complete('coder',prompt)
        edits = response.get('edits',[])
        self.check_shape(edits)
        self.record('coder','proposed',files=[x['path'] for x in edits])
        return {'edits':edits,'attempts':1,'error':'','stage_ok':False}

    def reviewer(self, state: WorkflowState) -> dict:
        """Independent LLM review and basic change-shape checks."""
        edits = state['edits']
        try:
            self.check_shape(edits)
            if len(edits) > len(state['scope']):
                raise ValueError('too many edits')
            review = self.model.complete('reviewer',
                'Review task and proposed file edits. Return {"approve":boolean,"reason":"..."}. '
                'Reject unnecessary edits. '+json.dumps({'task':self.task,'plan':state['plan'],
                                                            'edits':edits})[:70_000])
            approved = review.get('approve') is True
            reason = str(review.get('reason',''))[:300]
            if not approved:
                raise ValueError('review rejected change: '+reason)
            self.record('reviewer','approved',files=len(edits))
            return {'stage_ok':True,'error':''}
        except (ValueError,KeyError) as exc:
            self.record('reviewer','rejected',reason=str(exc)[:400])
            return {'stage_ok':False,'error':str(exc)[:400]}

    def security(self, state: WorkflowState) -> dict:
        try:
            for edit in state['edits']:
                validate_edit(self.workspace,edit['path'],edit['content'],scope=set(state['scope']))
            self.record('security','passed',files=len(state['edits']))
            return {'stage_ok':True,'error':''}
        except (ValueError,SyntaxError,OSError) as exc:
            self.record('security','blocked',reason=str(exc)[:400])
            return {'stage_ok':False,'error':'security: '+str(exc)[:400]}

    def tester(self, state: WorkflowState) -> dict:
        for edit in state['edits']:
            target = safe_path(self.workspace, edit['path'])
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(edit['content'],encoding='utf-8')
        outcome = run_tests(self.workspace,self.test_command,sandbox=self.sandbox,
                            allow_unsafe_local=self.allow_unsafe_local)
        self.record('tester','passed' if outcome.passed else 'failed',exit_code=outcome.exit_code,
                    attempts=state['attempts'],timed_out=outcome.timed_out)
        return {'passed':outcome.passed,'stage_ok':outcome.passed,
                'tests_output':outcome.output,
                'error':'' if outcome.passed else 'tests failed (exit '+str(outcome.exit_code)+')'}

    def debugger(self, state: WorkflowState) -> dict:
        response = self.model.complete('debugger',
            'Return JSON {"edits":[{"path":"...","content":"full UTF-8 file"}]}. '
            'Fix previous failing implementation without removing public definitions. '
            + json.dumps({'task':self.task,'scope':state['scope'],'error':state.get('error',''),
                          'test_output':state.get('tests_output','')[-5000:],
                          'files':snapshot(self.workspace,set(state['scope']))}))
        edits = response.get('edits',[])
        self.check_shape(edits)
        self.record('debugger','proposed_repair',attempt=state['attempts']+1,
                    files=[x['path'] for x in edits])
        return {'edits':edits, 'attempts':state['attempts']+1,'stage_ok':False}

    @staticmethod
    def check_shape(edits: list) -> None:
        if not isinstance(edits,list) or not edits or len(edits)>12 or any(
            not isinstance(x,dict) or not isinstance(x.get('path'),str) or
            not isinstance(x.get('content'),str) for x in edits):
            raise ValueError('model must return one to twelve complete file edits')
        if len({e['path'] for e in edits}) != len(edits):
            raise ValueError('duplicate edit paths')

    def retry_or_finish(self, state: WorkflowState) -> str:
        if state.get('stage_ok'):
            return 'next'
        return 'retry' if state['attempts'] <= self.max_retries else 'finish'

    def _native(self, state: WorkflowState) -> WorkflowState:
        state.update(self.planner(state))
        state.update(self.coder(state))
        while True:
            state.update(self.reviewer(state))
            if state['stage_ok']:
                state.update(self.security(state))
            if state['stage_ok']:
                state.update(self.tester(state))
            if state['stage_ok']:
                return state
            if state['attempts'] > self.max_retries:
                return state
            state.update(self.debugger(state))

    def _langgraph(self, state: WorkflowState) -> WorkflowState:
        try:
            from langgraph.graph import StateGraph, START, END
        except ImportError as exc:
            raise RuntimeError('Install the LangGraph extra: pip install -e ".[graph]"') from exc
        graph = StateGraph(WorkflowState)
        for name in ('planner','coder','reviewer','security','tester','debugger'):
            graph.add_node(name,getattr(self,name))
        graph.add_edge(START,'planner')
        graph.add_edge('planner','coder')
        graph.add_conditional_edges('reviewer',self._route_review,
                                    {'security':'security','debugger':'debugger','end':END})
        graph.add_conditional_edges('security',self._route_security,
                                    {'tester':'tester','debugger':'debugger','end':END})
        graph.add_conditional_edges('tester',self._route_test,
                                    {'debugger':'debugger','end':END})
        graph.add_edge('coder','reviewer')
        graph.add_edge('debugger','reviewer')
        return graph.compile().invoke(state,config={'recursion_limit':40})

    def _route_review(self,state):
        return 'security' if state['stage_ok'] else self._failed_route(state)

    def _route_security(self,state):
        return 'tester' if state['stage_ok'] else self._failed_route(state)

    def _route_test(self,state):
        return 'end' if state['stage_ok'] else self._failed_route(state)

    def _failed_route(self,state):
        return 'debugger' if state['attempts'] <= self.max_retries else 'end'

    def run(self, repository: Path, output_dir: Path) -> RunResult:
        repository, output_dir = Path(repository).resolve(),Path(output_dir).resolve()
        if output_dir.is_relative_to(repository):
            raise ValueError('output directory must be outside the input repository')
        if not repository.is_dir():
            raise ValueError('repository folder not found')
        output_dir.mkdir(parents=True, exist_ok=True)
        run_id = uuid.uuid4().hex[:12]
        self.trace = Trace(output_dir / (run_id + '.jsonl'))
        patch = output_dir / (run_id + '.patch')
        report = output_dir / (run_id + '.json')
        state: WorkflowState = {'attempts':0,'passed':False,'changed':[]}
        with tempfile.TemporaryDirectory(prefix='osdevin-') as temp:
            self.workspace = Path(temp) / 'workspace'
            copy_workspace(repository,self.workspace)
            try:
                result = self._langgraph(state) if self.graph=='langgraph' else self._native(state)
                state.update(result)
            except (Exception) as exc:
                # Persist trace/partial patch even when a provider or environment fails.
                state['error'] = f'{type(exc).__name__}: {exc}'
                state['passed'] = False
                self.record('orchestrator','error',reason=state['error'][:500])
            patch_text, changed = self._diff(repository,self.workspace)
            patch.write_text(patch_text,encoding='utf-8')
            state['changed'] = changed
        summary = {'success':bool(state.get('passed')),'attempts':state.get('attempts',0),
                   'changed_files':state['changed'],'error':state.get('error',''),
                   'workflow':self.graph,'sandbox':self.sandbox,
                   'trace':str(self.trace.path),'patch':str(patch)}
        report.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
        self.record('orchestrator','finished',success=summary['success'],attempts=summary['attempts'])
        return RunResult(summary['success'],summary['attempts'],changed,summary['error'],
                         patch,self.trace.path,report,self.graph)

    @staticmethod
    def _diff(original: Path, modified: Path) -> tuple[str,list[str]]:
        patches = []
        changes = []
        for file in sorted(modified.rglob('*')):
            if not file.is_file():
                continue
            rel = file.relative_to(modified).as_posix()
            src = original / rel
            if src.exists() and src.is_symlink():
                continue
            if file.suffix not in ('.py','.js','.ts','.tsx','.jsx','.json','.txt','.md','.yaml','.yml'):
                continue
            old = src.read_text(encoding='utf-8') if src.exists() else ''
            new = file.read_text(encoding='utf-8')
            if old == new:
                continue
            changes.append(rel)
            patches += list(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),
                                                 fromfile='a/'+rel,tofile='b/'+rel))
        return ''.join(patches),changes
