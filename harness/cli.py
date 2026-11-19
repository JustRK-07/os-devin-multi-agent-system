"""Command line entry point. Never modifies input repositories by default."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from harness.engine import Engine
from harness.llm.client import DemoModel, OpenAICompatibleModel, ModelError


REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_REPO = REPO_ROOT / 'evals' / 'tasks' / 'demo_calculator' / 'repo_before'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='OS Devin multi-role coding harness')
    subs = parser.add_subparsers(dest='action',required=True)
    for name in ('demo','run'):
        command = subs.add_parser(name)
        if name == 'run':
            command.add_argument('--repo',required=True,type=Path)
            command.add_argument('--task',required=True)
            command.add_argument('--test-command',default='python -m unittest discover -s tests -v')
        command.add_argument('--provider',choices=['demo','openai'],default='demo' if name=='demo' else 'openai')
        command.add_argument('--model',default='gpt-4o-mini')
        command.add_argument('--sandbox',choices=['docker','local'],default='docker')
        command.add_argument('--allow-unsafe-local',action='store_true')
        command.add_argument('--graph',choices=['native','langgraph'],default='native')
        command.add_argument('--max-retries',type=int,default=2)
        command.add_argument('--output',type=Path,default=Path('results/raw'))
    args = parser.parse_args(argv)
    if args.action == 'demo':
        repo = DEMO_REPO
        task = 'Fix calculator.add so it adds two numbers instead of subtracting them.'
        tests = 'python -m unittest discover -s tests -v'
    else:
        repo,task,tests=args.repo,args.task,args.test_command
        if args.provider == 'demo':
            parser.error('DemoModel only supports the built-in demo: use the demo subcommand')
    try:
        model = DemoModel() if args.provider=='demo' else OpenAICompatibleModel(args.model)
        runner = Engine(model,task=task,test_command=tests,sandbox=args.sandbox,
                        allow_unsafe_local=args.allow_unsafe_local,max_retries=args.max_retries,
                        graph=args.graph)
        result = runner.run(repo,args.output)
    except (ModelError,ValueError,OSError) as exc:
        print('ERROR:',exc,file=sys.stderr)
        return 2
    print(json.dumps({'success':result.success,'attempts':result.attempts,
                      'changed_files':result.changed_files,'error':result.error,
                      'patch':str(result.patch),'trace':str(result.trace),
                      'report':str(result.report)},indent=2))
    return 0 if result.success else 1


if __name__ == '__main__':
    sys.exit(main())
