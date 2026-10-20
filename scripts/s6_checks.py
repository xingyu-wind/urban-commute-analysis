"""Real warehouse verification; invoke inside s3_database.py with Docker available."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bigdata'))
from warehouse import snapshot, oracle, reconcile, publish, write_json, connect
from s6_edge_fixture import generate

START, END = '2026-10-15T00:00:00.000Z', '2026-10-17T00:00:00.000Z'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    steps = []
    def run(name, command, cwd=ROOT):
        with (output / (name + '.log')).open('x', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(name + ' failed; inspect log')
        steps.append(name)
        print('PASS ' + name, flush=True)
    maven = ['cmd', '/c', 'backend\\mvnw.cmd'] if os.name == 'nt' else ['bash', 'backend/mvnw']
    completed = False
    try:
        run('backend', maven + ['-f', 'backend/pom.xml', '-B', '-ntp', 'verify'])
        batches = []
        for name, fmt in [('csv', 'csv'), ('json', 'json'), ('repeat', 'csv')]:
            destination = output / name
            run('etl-' + name, [sys.executable, '-m', 'commute_etl', '--config', str(ROOT / f'data-pipeline/examples/{fmt}-config.json'),
                '--input', str(ROOT / f'data-pipeline/examples/traffic.{fmt}'), '--batch', 's6-' + name, '--load', '--output', str(destination)], ROOT / 'data-pipeline')
            batches.append(destination)
        edge = generate(ROOT, output / 'edge-fixture')
        run('etl-edge', [sys.executable, '-m', 'commute_etl', '--config', str(edge / 'config.json'), '--input', str(edge / 'traffic.json'), '--batch', 's6-edge', '--load', '--output', str(output / 'edge')], ROOT / 'data-pipeline')
        batches.append(output / 'edge')
        bundle = output / 'bundle'
        manifest = snapshot(batches, bundle, START, END)
        expected = oracle(bundle)
        write_json(output / 'oracle.json', expected)
        assert manifest['ods_count'] == 39 and manifest['unique_count'] == 21
        checks = {(r['target_type'], r['target_id']): (r['sample_count'], r['avg_speed_kmh'], r['congestion_index'])
                  for r in expected if r['grain'] == 'WINDOW' and r['dataset_id'] == 's5-synthetic-v1'}
        assert checks['CITY', 's5-city'] == ('3', '40.00', '5.00')
        assert checks['REGION', 's5-east'] == ('2', '36.00', '3.00')
        assert checks['ROAD', 's5-road'] == ('2', '18.00', '3.00')
        edge_city = next(r for r in expected if r['dataset_id'] == 's6-edge-v2' and r['target_id'] == 's5-city' and r['grain'] == 'WINDOW')
        assert edge_city['sample_count'] == '6' and edge_city['avg_speed_kmh'] == '41.67'
        edge_hour = next(r for r in expected if r['dataset_id'] == 's6-edge-v2' and r['target_type'] == 'REGION' and r['grain'] == 'HOUR' and r['bucket_start'] == '2026-10-16T01:00:00.000Z')
        assert edge_hour['avg_speed_kmh'] == '1.01'
        evidence = output / 'hive'
        evidence.mkdir()
        # Official image; no ports, privileged mode, or host data volumes.
        image = 'apache/hive:4.1.0'
        run('docker-pull', ['docker', 'pull', image])
        run('image-inspect', ['docker', 'image', 'inspect', image])
        run('real-hive', ['docker', 'run', '--rm', '--user', '0:0', '--entrypoint', 'bash',
            '-e', 'GITHUB_ACTIONS=' + os.environ.get('GITHUB_ACTIONS', ''), '-e', 'S6_ALLOW_EMPTY_FORMAT=' + os.environ.get('S6_ALLOW_EMPTY_FORMAT', ''),
            '-e', 'S6_FROM=' + START, '-e', 'S6_TO=' + END,
            '-v', str(ROOT) + ':/source:ro', '-v', str(bundle) + ':/bundle:ro', '-v', str(evidence) + ':/evidence',
            image, '/source/bigdata/runner/isolated-hive.sh'])
        rows = reconcile(bundle, evidence / 'ads-first.tsv')
        assert rows == reconcile(bundle, evidence / 'ads-repeat.tsv')
        write_json(output / 'hive-reconciliation.json', {'passed': True, 'ods': manifest['ods_count'], 'dwd': manifest['unique_count'], 'ads': len(rows), 'rows': rows})
        releases = [publish(bundle, evidence / 'ads-first.tsv', 's6-first'), publish(bundle, evidence / 'ads-first.tsv', 's6-first')]
        assert releases[0]['reused'] is False and releases[1]['reused'] is True
        visible = 's6-first'
        for failure in ('insert', 'switch'):
            try:
                publish(bundle, evidence / 'ads-first.tsv', 's6-failed-' + failure, fail_at=failure)
                raise AssertionError('failure injection did not fail')
            except RuntimeError as error:
                assert 'injected' in str(error)
            connection = connect()
            with connection.cursor() as cur:
                cur.execute('SELECT release_id FROM warehouse_current')
                assert cur.fetchone()['release_id'] == visible
                cur.execute('SELECT COUNT(*) n FROM warehouse_metric WHERE release_id=%s', ('s6-failed-' + failure,))
                assert cur.fetchone()['n'] == 0
            connection.close()
            releases.append(publish(bundle, evidence / 'ads-first.tsv', 's6-failed-' + failure))
            visible = 's6-failed-' + failure
        write_json(output / 'publication.json', releases)
        # CLI candidates, altered checksums, and non-SUCCEEDED batch reports fail closed.
        bad = output / 'bad-candidate'
        shutil.copytree(batches[0], bad)
        altered = json.loads((bad / 'normalized.json').read_text(encoding='utf-8'))
        altered[0]['avg_speed_kmh'] = '249.00'
        write_json(bad / 'normalized.json', altered)
        try:
            snapshot([bad], output / 'rejected-snapshot', START, END)
            raise AssertionError('tampered candidates admitted')
        except ValueError as error:
            assert 'lineage' in str(error)
        run('browser', ['node', 'frontend/scripts/verify-s6.mjs', str(output / 'browser')])
        completed = True
        return 0
    finally:
        write_json(output / 'summary.json', {'passed': completed, 'steps': steps})


if __name__ == '__main__':
    sys.exit(main())
