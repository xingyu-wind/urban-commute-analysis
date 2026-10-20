"""S5 suite; run inside s3_database.py, after dependency installation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--with-core', action='store_true', help='Run S2-S4 regression before S5 in this fresh schema')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    def run(name, command, env=None):
        with (output / (name + '.log')).open('x', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        results.append({'name': name, 'exitCode': result.returncode})
        if result.returncode:
            raise RuntimeError(name + ' failed; inspect ' + str(output / (name + '.log')))
        print('PASS ' + name, flush=True)
    try:
        maven = ['cmd', '/c', 'backend\\mvnw.cmd'] if os.name == 'nt' else ['bash', 'backend/mvnw']
        if args.with_core:
            run('core', [sys.executable, 'scripts/s4_checks.py', '--with-core', '--output', str(output / 'core')])
        else:
            run('flyway-backend', maven + ['-f', 'backend/pom.xml', '-B', '-ntp', 'verify'])
        run('pytest', [sys.executable, '-m', 'pytest', 'data-pipeline', '-q', '--junitxml=' + str(output / 'pytest.xml')])
        fixture = output / 'ui-fixture'
        run('prepare', [sys.executable, 'scripts/s5_browser_data.py', 'prepare', '--output', str(fixture)])
        env = {**os.environ, 'S5_FIXTURE_OUTPUT': str(fixture), 'CONTRACT_PYTHON': sys.executable}
        run('browser', ['node', 'frontend/scripts/verify-s4.mjs', str(output / 'browser')], env)
        run('schemas', [sys.executable, 'scripts/s4_validate_captures.py', str(output / 'browser')])
        return 0
    finally:
        (output / 'summary.json').write_text(json.dumps({'passed': len(results) == 5 and all(r['exitCode'] == 0 for r in results), 'commands': results}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
