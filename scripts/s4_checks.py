"""Real S4 SQL, Java HTTP, Chromium and schema regression after the S2/S3 regression.

Invoke inside s3_database.py's child environment. No database destruction or request mocking.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--with-core', action='store_true', help='Run full S2/S3/backend/frontend checks first')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []

    def run(name, command):
        with (output / (name + '.log')).open('x', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        results.append({'name': name, 'command': command, 'exitCode': result.returncode})
        if result.returncode:
            raise RuntimeError(name + ' failed; see ' + str(output / (name + '.log')))
        print('PASS ' + name, flush=True)

    try:
        if args.with_core:
            run('core', [sys.executable, 'scripts/s3_checks.py', '--output', str(output / 'core')])
        run('fixture', [sys.executable, 'scripts/s4_database.py', 'fixture'])
        run('oracle', [sys.executable, 'scripts/s4_database.py', 'oracle'])
        run('browser', ['node', 'frontend/scripts/verify-s4.mjs', str(output / 'browser')])
        run('schemas', [sys.executable, 'scripts/s4_validate_captures.py', str(output / 'browser')])
        run('oracle-restored', [sys.executable, 'scripts/s4_database.py', 'oracle'])
        return 0
    finally:
        (output / 'summary.json').write_text(json.dumps({'commands': results, 'passed': len(results) == (6 if args.with_core else 5)
            and all(r['exitCode'] == 0 for r in results)}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
