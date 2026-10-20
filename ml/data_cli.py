"""Controlled offline V3.2 commands; real raw inspection output stays in ignored storage."""
import argparse
import json
import os
from pathlib import Path
import sys

from data_adapter import inspect_file, inspect_zenodo_v6, confirm, convert, ROOT
from domain_evaluation import suitability, evaluate, transfer


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['inspect', 'inspect-zenodo-v6', 'confirm', 'convert', 'quality', 'evaluate', 'transfer'])
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--review', type=Path)
    p.add_argument('--config', type=Path)
    p.add_argument('--target', type=Path)
    p.add_argument('--distribution-file', choices=['METR-LA.csv', 'PEMS-BAY.csv'])
    p.add_argument('--actor')
    p.add_argument('--acknowledgement')
    p.add_argument('--synthetic-fixture', action='store_true', help='Explicit assertion for repository-owned synthetic test inputs only')
    args = p.parse_args()
    try:
        if args.action in ('inspect', 'inspect-zenodo-v6'):
            private = any(args.input.resolve().is_relative_to(ROOT / 'data' / d) for d in ('raw', 'private', 'external'))
            controlled_output = any(args.output.resolve().is_relative_to(ROOT / 'data' / d) for d in ('raw', 'private', 'external'))
            if (not args.synthetic_fixture and (not private or not controlled_output or os.environ.get('GITHUB_ACTIONS'))) or (private and (os.environ.get('GITHUB_ACTIONS') or not controlled_output)):
                raise ValueError('external raw inspection cannot go to CI artifacts/tracked output; use controlled local storage')
            value = inspect_file(args.input) if args.action == 'inspect' else inspect_zenodo_v6(args.input, args.distribution_file)
        elif args.action == 'confirm':
            if not args.review or not args.actor or not args.acknowledgement: p.error('confirm requires --review --actor --acknowledgement')
            value = confirm(load(args.input), load(args.review), args.actor, args.acknowledgement)
        elif args.action == 'convert':
            if not args.config: p.error('convert requires --config')
            private = any(args.input.resolve().is_relative_to(ROOT / 'data' / d) for d in ('raw', 'private', 'external'))
            controlled_output = any(args.output.resolve().is_relative_to(ROOT / 'data' / d) for d in ('raw', 'private', 'external'))
            if private and (os.environ.get('GITHUB_ACTIONS') or not controlled_output): raise ValueError('private raw data cannot be exported')
            value = convert(args.input, load(args.config))
        elif args.action == 'quality': value = suitability(load(args.input))
        elif args.action == 'evaluate': value = evaluate(load(args.input))
        else:
            if not args.target: p.error('transfer requires --target normalized dataset')
            value = transfer(load(args.input), load(args.target))
        # Never export normalized external records to a tracked/CI-output path.
        if args.action == 'convert' and value['source_type'] != 'synthetic_test':
            if os.environ.get('GITHUB_ACTIONS') or not any(args.output.resolve().is_relative_to(ROOT / 'data' / d) for d in ('raw', 'private', 'external')):
                raise ValueError('external normalized rows must remain in controlled local storage')
        save(args.output, value)
        print(json.dumps(dict(action=args.action, status=value.get('status', value.get('state', value.get('contract'))), saved=True)))
        return 0
    except (ValueError, KeyError, OSError) as error:
        print('Data operation refused: ' + type(error).__name__ + ': ' + str(error)[:200], file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
