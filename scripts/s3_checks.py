"""Complete local regression under the fresh schema environment from s3_database.py."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []

    def run(name, command, cwd=ROOT):
        print('RUN ' + name, flush=True)
        with (output / (name + '.log')).open('x', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        results.append({'name': name, 'command': command, 'exitCode': result.returncode})
        if result.returncode:
            raise RuntimeError(name + ' failed; see ' + str(output / (name + '.log')))
        print('PASS ' + name, flush=True)

    npm = ['cmd', '/c', 'npm'] if os.name == 'nt' else ['npm']
    maven = (['cmd', '/c', 'backend\\mvnw.cmd'] if os.name == 'nt' else ['bash', 'backend/mvnw'])
    try:
        run('backend', maven + ['-f', 'backend/pom.xml', '-B', '-ntp', 'verify'])
        run('ci-policy', [sys.executable, 'scripts/check_ci.py'])
        run('openapi', [sys.executable, '-m', 'openapi_spec_validator', 'contracts/openapi.yaml'])
        run('contract', [sys.executable, 'contracts/validate_contract.py'])
        run('http', [sys.executable, 'backend/scripts/verify_http.py', '--output', str(output / 'http')])
        run('types', npm + ['run', 'type-check'], ROOT / 'frontend')
        run('frontend-unit', npm + ['test', '--', '--reporter=json', '--outputFile=' + str(output / 'frontend-unit.json')], ROOT / 'frontend')
        run('build', npm + ['run', 'build'], ROOT / 'frontend')
        run('browser', npm + ['run', 'test:e2e', '--', str(output / 'browser')], ROOT / 'frontend')
        run('negative-driver', [sys.executable, 'scripts/check-regression-failures.py', str(output / 'browser'), str(output / 'negative')], ROOT / 'frontend')
        match = re.fullmatch(r'jdbc:mysql://127\.0\.0\.1:(\d+)/(s3test_[0-9a-f]{32})\?connectionTimeZone=UTC', os.environ['DB_URL'])
        if not match:
            raise RuntimeError('Evidence query requires the isolated datasource')
        env = os.environ.copy()
        env['MYSQL_PWD'] = env['DB_PASSWORD']
        query = "SELECT VERSION(), DATABASE(), @@time_zone; SHOW TABLES; SELECT version,checksum,success FROM flyway_schema_history ORDER BY installed_rank; SELECT COUNT(*) AS cities FROM city; SELECT COUNT(*) AS observations FROM traffic_observation;"
        query += ''.join(' SHOW CREATE TABLE ' + table + ';' for table in ('dataset_registry', 'city', 'region', 'road_segment', 'traffic_observation'))
        result = subprocess.run([os.environ.get('MYSQL_CLIENT', 'mysql'), '--no-defaults', '--no-login-paths', '--protocol=TCP', '-h127.0.0.1', '-P' + match[1], '-u' + env['DB_USER'], match[2], '--default-character-set=utf8mb4', '--batch'], input=query, text=True, encoding='utf-8', capture_output=True, env=env)
        if result.returncode:
            raise RuntimeError('Read-only database evidence query failed')
        (output / 'database.txt').write_text(result.stdout, encoding='utf-8')
        tests = [ET.parse(path).getroot() for path in (ROOT / 'backend/target/surefire-reports').glob('TEST-*.xml')]
        counts = {key: sum(int(test.attrib[key]) for test in tests) for key in ('tests','failures','errors','skipped')}
        unit = json.loads((output / 'frontend-unit.json').read_text(encoding='utf-8'))
        summary = {'backend': counts, 'frontend': {key: unit[key] for key in ('numTotalTests','numPassedTests','numFailedTests')}, 'mysql': result.stdout.splitlines()[1].split('\t')[0], 'commands': results, 'exitCode': 0}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        return 0
    except Exception as error:
        (output / 'failure.json').write_text(json.dumps({'error': str(error), 'commands': results}, indent=2), encoding='utf-8')
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
