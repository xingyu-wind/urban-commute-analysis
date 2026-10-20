"""S5 suite; run inside s3_database.py, after dependency installation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data-pipeline'))


def audit_snapshot(output):
    """Read-only reconciliation against committed MySQL records, without credentials."""
    from commute_etl.store import connect
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT b.*,COUNT(l.observation_id) lineage_count,'
                "SUM(CASE WHEN l.disposition='WRITTEN' THEN 1 ELSE 0 END) linked_written,"
                "SUM(CASE WHEN l.disposition='EXISTING' THEN 1 ELSE 0 END) linked_existing,"
                '(SELECT COUNT(*) FROM etl_rejection r WHERE r.batch_id=b.batch_id) rejection_rows '
                'FROM etl_batch b LEFT JOIN etl_batch_observation l ON l.batch_id=b.batch_id '
                'GROUP BY b.batch_id ORDER BY b.batch_id')
            batches = cursor.fetchall()
            for batch in batches:
                assert batch['input_count'] == batch['accepted_count'] + batch['rejected_count'] + batch['duplicate_count']
                assert batch['rejected_count'] == batch['rejection_rows']
                if batch['status'] == 'SUCCEEDED':
                    assert batch['accepted_count'] == batch['written_count'] + batch['existing_count'] == batch['lineage_count']
                    assert batch['written_count'] == batch['linked_written']
                    assert batch['existing_count'] == batch['linked_existing']
                else:
                    assert batch['written_count'] == batch['existing_count'] == batch['lineage_count'] == 0
            cursor.execute('SELECT dataset_id,target_type,target_id,COUNT(*) n,SUM(avg_speed_kmh)/COUNT(*) speed,'
                           'SUM(congestion_index)/COUNT(*) congestion FROM traffic_observation '
                           'WHERE dataset_id LIKE %s GROUP BY dataset_id,target_type,target_id ORDER BY dataset_id,target_type,target_id', ('s5-%',))
            observations = cursor.fetchall()
            cursor.execute('SELECT version,checksum,success FROM flyway_schema_history ORDER BY installed_rank')
            migrations = cursor.fetchall()
        (output / 'mysql-reconciliation.json').write_text(json.dumps({'reconciled': True, 'batches': batches,
            'observations': observations, 'migrations': migrations}, default=str, indent=2) + '\n', encoding='utf-8')
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--with-core', action='store_true', help='Run S2-S4 regression before S5 in this fresh schema')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    completed = False
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
        audit_snapshot(output)
        completed = True
        return 0
    finally:
        (output / 'summary.json').write_text(json.dumps({'passed': completed and len(results) == 5 and all(r['exitCode'] == 0 for r in results), 'commands': results}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
