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
    parser.add_argument('--admission-only', action='store_true', help='Local MySQL/Decimal checks only; explicitly does NOT claim Hive execution')
    parser.add_argument('--hive-evidence', type=Path, help='Reuse downloaded real Hive evidence; still independently reconcile every exported value')
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
        edge_batch = json.loads((output / 'edge/batch.json').read_text(encoding='utf-8'))
        assert edge_batch['accepted_count'] == 12 and edge_batch['rejected_count'] == 2
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
        negatives = []
        def reject(name, action):
            try:
                action()
            except ValueError:
                negatives.append(name)
                return
            raise AssertionError(name + ' was not rejected')
        bad = output / 'bad-candidate'
        shutil.copytree(batches[0], bad)
        altered = json.loads((bad / 'normalized.json').read_text(encoding='utf-8'))
        altered[0]['avg_speed_kmh'] = '249.00'
        write_json(bad / 'normalized.json', altered)
        reject('altered-candidate', lambda: snapshot([bad], output / 'rejected-candidate', START, END))
        report = json.loads((bad / 'batch.json').read_text(encoding='utf-8'))
        report['status'] = 'FAILED'
        write_json(bad / 'batch.json', report)
        reject('failed-batch', lambda: snapshot([bad], output / 'rejected-batch', START, END))
        reject('duplicate-batch-directory', lambda: snapshot([batches[0], batches[0]], output / 'rejected-duplicate', START, END))
        write_json(output / 'admission.json', {'passed': True, 'ods': manifest['ods_count'], 'unique': manifest['unique_count'], 'negativeCases': negatives})
        if args.admission_only:
            completed = True
            return 0
        evidence = output / 'hive'
        if args.hive_evidence:
            shutil.copytree(args.hive_evidence, evidence)
        else:
            evidence.mkdir()
        # Official image; no ports, privileged mode, or host data volumes.
        image = 'apache/hive:4.1.0@sha256:b957bb0e698e560d24e162b7549d79f191d58703e92899a886618c317f6e8f30'
        if not args.hive_evidence:
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
        reordered = output / 'ads-reordered.tsv'
        reordered.write_text('\n'.join(reversed((evidence / 'ads-first.tsv').read_text(encoding='utf-8').splitlines())) + '\n', encoding='utf-8')
        assert publish(bundle, reordered, 's6-first')['reused'] is True
        incomplete = output / 'ads-incomplete.tsv'
        incomplete.write_text('\n'.join((evidence / 'ads-first.tsv').read_text(encoding='utf-8').splitlines()[:-1]) + '\n', encoding='utf-8')
        reject('incomplete-hive-export', lambda: publish(bundle, incomplete, 's6-invalid'))
        stale = output / 'stale-bundle'
        shutil.copytree(bundle, stale)
        stale_manifest = json.loads((stale / 'manifest.json').read_text(encoding='utf-8'))
        stale_manifest['captured_at'] = '2020-01-01T00:00:00.000Z'
        write_json(stale / 'manifest.json', stale_manifest)
        reject('stale-snapshot', lambda: publish(stale, evidence / 'ads-first.tsv', 's6-stale'))
        reject('release-id-conflict', lambda: publish(stale, evidence / 'ads-first.tsv', 's6-first'))
        visible = 's6-first'
        for failure in ('insert', 'commit', 'switch'):
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
        write_json(output / 'negative-cases.json', negatives)
        try:
            publish(bundle, evidence / 'ads-first.tsv', 's6-remains-failed', fail_at='commit')
            raise AssertionError('final failed release was published')
        except RuntimeError as error:
            assert 'injected' in str(error)
        connection = connect()
        with connection.cursor() as cur:
            cur.execute('SELECT release_id FROM warehouse_current')
            assert cur.fetchone()['release_id'] == visible
            cur.execute('SELECT release_id,status,row_count,published_at FROM warehouse_release ORDER BY release_id')
            status_rows = cur.fetchall()
            cur.execute('SELECT release_id,grain,COUNT(*) metric_rows,SUM(sample_count) samples,SUM(speed_sum) speed_sum,SUM(congestion_sum) congestion_sum '
                'FROM warehouse_metric GROUP BY release_id,grain ORDER BY release_id,grain')
            totals = cur.fetchall()
        connection.close()
        write_json(output / 'mysql-reconciliation.json', {'releases': status_rows, 'totals': totals, 'visible': visible, 'passed': True})
        run('browser', ['node', 'frontend/scripts/verify-s6.mjs', str(output / 'browser')])
        completed = True
        return 0
    finally:
        write_json(output / 'summary.json', {'passed': completed, 'scope': 'mysql-admission-only' if args.admission_only else 'real-hive-chain',
            'hiveEvidenceReused': str(args.hive_evidence) if args.hive_evidence else None, 'steps': steps})


if __name__ == '__main__':
    sys.exit(main())
