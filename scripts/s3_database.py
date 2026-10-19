"""Provision a NEW isolated schema/account, then run a child with private DB environment.

No DROP, cleanup, or reuse of existing schemas. Use only an authorized local/CI instance.
Admin credentials arrive via environment, never command arguments or evidence files.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--probe-isolation', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Refusing to overwrite prior evidence')
    host = os.environ.get('S3_MYSQL_HOST', '127.0.0.1')
    if host != '127.0.0.1':
        raise RuntimeError('Only an explicitly isolated loopback instance is allowed')
    port = int(os.environ.get('S3_MYSQL_PORT', '33067'))
    schema = 's3test_' + uuid.uuid4().hex
    user = 's3t_' + secrets.token_hex(10)
    password = secrets.token_hex(24)
    client = os.environ.get('MYSQL_CLIENT', 'mysql')
    admin_env = os.environ.copy()
    admin_env['MYSQL_PWD'] = os.environ['S3_ADMIN_PASSWORD']
    command = [client, '--no-defaults', '--no-login-paths', '--protocol=TCP',
               '-h' + host, '-P' + str(port), '-u' + os.environ.get('S3_ADMIN_USER', 'root'),
               '--batch', '--skip-column-names', '--default-character-set=utf8mb4']

    def sql(text):
        result = subprocess.run(command, input=text, text=True, encoding='utf-8',
                                capture_output=True, env=admin_env)
        if result.returncode:
            # Never echo SQL or authentication diagnostics into public logs.
            raise RuntimeError('Isolated database provisioning failed; no existing objects were removed')
        return result.stdout.strip()

    version, server_uuid = sql('SELECT VERSION(), @@server_uuid;').split('\t')
    if not version.startswith('8.4.'):
        raise RuntimeError('S3 requires real MySQL 8.4')
    grant_schema = schema.replace('_', '\\_')
    sql(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;\n"
        f"CREATE USER '{user}'@'%' IDENTIFIED BY '{password}';\n"
        f"GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,REFERENCES ON `{grant_schema}`.* TO '{user}'@'%';")
    env = {k: v for k, v in os.environ.items() if k not in ('S3_ADMIN_PASSWORD', 'MYSQL_PWD')}
    url = f'jdbc:mysql://{host}:{port}/{schema}?connectionTimeZone=UTC'
    env.update(TEST_DB_URL=url, TEST_DB_USER=user, TEST_DB_PASSWORD=password,
               TEST_DB_SCHEMA=schema, TEST_DB_SERVER_UUID=server_uuid,
               DB_URL=url, DB_USER=user, DB_PASSWORD=password)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    evidence = {'mysqlVersion': version, 'schema': schema, 'account': user,
                'serverUuid': server_uuid, 'newSchema': True, 'newScopedAccount': True,
                'existingDataDeleted': False}
    # For CI subsequent standalone HTTP and browser processes, not uploaded as an artifact.
    if os.environ.get('GITHUB_ENV'):
        with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as output:
            for key in ('DB_URL', 'DB_USER', 'DB_PASSWORD'):
                output.write(f'{key}={env[key]}\n')
        print('::add-mask::' + password, flush=True)
    child = args.command
    if child and child[0] == '--':
        child = child[1:]
    if not child:
        raise RuntimeError('Provide a verification command after --')
    try:
        if args.probe_isolation:
            evidence['rejectedBeforeMigration'] = []
            probes = [('TEST_DB_SCHEMA', 's3test_' + uuid.uuid4().hex, 'Actual MySQL test identity mismatch'),
                      ('TEST_DB_SERVER_UUID', str(uuid.uuid4()), 'Actual MySQL test identity mismatch'),
                      ('TEST_DB_URL', f'jdbc:mysql://{host}:{port}/urban_commute?connectionTimeZone=UTC',
                       'Refusing non-isolated test JDBC URL')]
            for key, wrong, expected_message in probes:
                probe_env = {**env, key: wrong}
                log_path = args.output.with_name(args.output.stem + '-' + key + '.log')
                with log_path.open('x', encoding='utf-8') as log:
                    probe = subprocess.run(child, env=probe_env, stdout=log, stderr=subprocess.STDOUT)
                count = int(sql(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='{schema}';"))
                text = log_path.read_text(encoding='utf-8', errors='replace')
                if probe.returncode == 0 or count != 0 or expected_message not in text:
                    raise RuntimeError('Isolation probe did not fail closed before schema writes')
                evidence['rejectedBeforeMigration'].append({'setting': key, 'tableCountAfter': count})
                print('PASS migration blocked before writes: ' + key, flush=True)
        result = subprocess.run(child, env=env)
        evidence['exitCode'] = result.returncode
        return result.returncode
    finally:
        args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
