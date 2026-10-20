"""S4 fixture/oracle/mutation helper, exclusively for newly provisioned s3test schemas.

Uses the child environment from s3_database.py. Never uses admin credentials, DROP or DELETE.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sql(statement):
    match = re.fullmatch(r'jdbc:mysql://127\.0\.0\.1:(\d+)/(s3test_[0-9a-f]{32})\?connectionTimeZone=UTC', os.environ['DB_URL'])
    if not match or not re.fullmatch(r's3t_[0-9a-f]{20}', os.environ['DB_USER']):
        raise RuntimeError('Refusing non-isolated S4 database')
    env = os.environ.copy()
    env['MYSQL_PWD'] = env['DB_PASSWORD']
    env['MYSQL_TEST_LOGIN_FILE'] = str(ROOT / 'backend/target/s4-no-login.cnf')
    command = [env.get('MYSQL_CLIENT', 'mysql'), '--no-defaults', '--protocol=TCP', '-h127.0.0.1',
               '-P' + match[1], '-u' + env['DB_USER'], match[2], '--batch', '--skip-column-names', '--default-character-set=utf8mb4']

    def execute(text):
        result = subprocess.run(command, input=text, text=True, encoding='utf-8', capture_output=True, env=env)
        if result.returncode:
            raise RuntimeError('S4 scoped SQL failed; connection diagnostics suppressed')
        return result.stdout.strip()

    identity = execute('SELECT DATABASE(),SUBSTRING_INDEX(CURRENT_USER(),\'@\',1),VERSION(),@@server_uuid;').split('\t')
    if len(identity) != 4 or identity[:2] != [match[2], env['DB_USER']] or not identity[2].startswith('8.4.'):
        raise RuntimeError('Actual S4 database identity mismatch')
    if env.get('TEST_DB_SERVER_UUID') and identity[3] != env['TEST_DB_SERVER_UUID']:
        raise RuntimeError('Actual S4 server UUID mismatch')
    return execute(statement)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['fixture', 'oracle', 'mutate', 'restore'])
    args = parser.parse_args()
    if args.action == 'fixture':
        # Fixture deliberately fails on existing IDs, preventing a stale import from passing silently.
        sql((ROOT / 'database/fixtures/s4-synthetic.sql').read_text(encoding='utf-8'))
        print('S4 synthetic fixture inserted into owned isolated schema')
    elif args.action == 'oracle':
        actual = sql((ROOT / 'database/fixtures/s4-expected.sql').read_text(encoding='utf-8'))
        rows = [line.split('\t') for line in actual.splitlines()]
        expected = [('CITY', 's4-demo-city', 3, 36, 5), ('REGION', 's4-demo-east', 2, 25, 6),
                    ('REGION', 's4-demo-west', 1, 50, 2), ('ROAD', 's4-demo-road-a', 2, 15, 8),
                    ('ROAD', 's4-demo-road-b', 1, 40, 3)]
        if len(rows) != 7:
            raise RuntimeError('Independent SQL oracle row count mismatch')
        for row, wanted in zip(rows[:5], expected):
            if row[:2] != list(wanted[:2]) or [float(v) for v in row[2:5]] != list(wanted[2:]):
                raise RuntimeError('Independent SQL oracle differs from hand calculation')
        for row, wanted in zip(rows[5:], [('2026-10-15', 2, 36, 5), ('2026-10-16', 1, 36, 5)]):
            if row[0] != wanted[0] or [float(v) for v in row[1:]] != list(wanted[1:]):
                raise RuntimeError('Independent daily SQL oracle mismatch')
        print(json.dumps({'handCalculationMatched': True, 'sqlRows': rows}, ensure_ascii=False, indent=2))
    else:
        before, after = (42, 60) if args.action == 'mutate' else (60, 42)
        predicate = "dataset_id='s4-synthetic-v1' AND city_id='s4-demo-city' AND target_type='CITY' AND observed_at='2026-10-15 09:00:00'"
        if sql('SELECT COUNT(*) FROM traffic_observation WHERE ' + predicate + f' AND avg_speed_kmh={before};') != '1':
            raise RuntimeError('Controlled synthetic mutation precondition mismatch')
        result = sql('UPDATE traffic_observation SET avg_speed_kmh=' + str(after) + ' WHERE ' + predicate
                     + f' AND avg_speed_kmh={before}; SELECT ROW_COUNT();')
        if result != '1':
            raise RuntimeError('Controlled synthetic mutation did not affect exactly one row')
        print(json.dumps({'action': args.action, 'affectedRows': 1, 'before': before, 'after': after}))


if __name__ == '__main__':
    main()
