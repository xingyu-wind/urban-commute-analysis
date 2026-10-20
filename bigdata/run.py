"""Explicit S6 CLI. Requires the same isolated TEST_DB_* environment as S5."""
import argparse
from pathlib import Path
from warehouse import snapshot, reconcile, publish, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    admission = commands.add_parser('snapshot')
    admission.add_argument('--batch-dir', type=Path, action='append', required=True)
    admission.add_argument('--output', type=Path, required=True)
    admission.add_argument('--from', dest='start', required=True)
    admission.add_argument('--to', dest='end', required=True)
    for name in ('reconcile', 'publish'):
        command = commands.add_parser(name)
        command.add_argument('--bundle', type=Path, required=True)
        command.add_argument('--ads', type=Path, required=True)
        if name == 'publish':
            command.add_argument('--release', required=True)
    args = parser.parse_args()
    if args.command == 'snapshot':
        result = snapshot(args.batch_dir, args.output, args.start, args.end)
    elif args.command == 'reconcile':
        result = {'reconciled': True, 'rows': len(reconcile(args.bundle, args.ads))}
    else:
        result = publish(args.bundle, args.ads, args.release)
    import json
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
