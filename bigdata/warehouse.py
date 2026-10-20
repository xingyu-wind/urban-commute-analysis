"""S6 snapshot admission, independent Decimal oracle, and atomic ADS publication.

The S5 loader remains the only ETL. This module consumes its committed lineage.
Database access deliberately inherits S5's isolated database identity gate.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data-pipeline'))
from commute_etl.clean import OUTPUT_FIELDS, canonical
from commute_etl.store import connect, db_values

FIELDS = ['observation_id', *OUTPUT_FIELDS, 'dataset_version', 'source_type', 'source_sha256', 'batch_id', 'road_region_id']
ADS_FIELDS = ['dataset_id', 'dataset_version', 'source_type', 'city_id', 'target_type', 'target_id',
              'road_region_id', 'grain', 'bucket_start', 'sample_count', 'speed_sum', 'congestion_sum',
              'avg_speed_kmh', 'congestion_index', 'observed_from', 'observed_to']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def stamp(value):
    return value.replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def timestamp(value):
    if not re.fullmatch(r'20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', value):
        raise ValueError('expected canonical UTC milliseconds')
    return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)


def snapshot(inputs, output, start, end):
    """Each input is an S5 output directory; compare ALL candidates to DB lineage.

    One repeatable-read transaction captures source, batch, dimensions and rows.
    File artifacts alone never qualify a batch or an observation for the warehouse.
    """
    start_time, end_time = timestamp(start), timestamp(end)
    if not start_time < end_time:
        raise ValueError('invalid half-open window')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    connection = connect()
    records, batches, seen_batches = [], [], set()
    try:
        connection.begin()
        with connection.cursor() as cur:
            for directory in map(Path, inputs):
                candidate = json.loads((directory / 'normalized.json').read_text(encoding='utf-8'))
                report = json.loads((directory / 'batch.json').read_text(encoding='utf-8'))
                source = json.loads((directory / 'source.json').read_text(encoding='utf-8'))
                batch_id = report['batch_id']
                if batch_id in seen_batches:
                    raise ValueError('duplicate batch input')
                seen_batches.add(batch_id)
                cur.execute('SELECT b.*,s.manifest,s.dataset_id,d.dataset_version,d.source_type '
                            'FROM etl_batch b JOIN etl_source s USING(source_sha256) '
                            'JOIN dataset_registry d ON d.dataset_id=s.dataset_id WHERE batch_id=%s', (batch_id,))
                batch = cur.fetchone()
                if not batch or batch['status'] != 'SUCCEEDED' or report['status'] != 'SUCCEEDED':
                    raise ValueError('batch is not committed SUCCEEDED')
                if (json.loads(batch['manifest']) != source or batch['source_sha256'] != hashlib.sha256(canonical(source).encode()).hexdigest()
                        or report['source_sha256'] != batch['source_sha256'] or report['file_sha256'] != batch['file_sha256']):
                    raise ValueError('source or batch identity mismatch')
                cur.execute('SELECT o.*,r.region_id road_region_id FROM etl_batch_observation l '
                            'JOIN traffic_observation o ON o.id=l.observation_id '
                            'LEFT JOIN road_segment r ON r.id=o.road_segment_id AND r.city_id=o.city_id '
                            'WHERE l.batch_id=%s ORDER BY o.id', (batch_id,))
                linked = cur.fetchall()
                values = {db_values(row) for row in candidate}
                if len(values) != len(candidate) or len(linked) != batch['accepted_count'] or values != {tuple(r[f] for f in OUTPUT_FIELDS) for r in linked}:
                    raise ValueError('candidate differs from committed observation lineage')
                if batch['source_type'] not in ('synthetic_test', 'historical_snapshot', 'authorized_live'):
                    raise ValueError('unadmitted source')
                for row in linked:
                    if row['dataset_id'] != batch['dataset_id']:
                        raise ValueError('dataset lineage mismatch')
                    if not start_time <= row['observed_at'] < end_time:
                        continue
                    item = {'observation_id': row['id'], **{f: row[f] for f in OUTPUT_FIELDS},
                            'dataset_version': batch['dataset_version'], 'source_type': batch['source_type'],
                            'source_sha256': batch['source_sha256'], 'batch_id': batch_id,
                            'road_region_id': row['road_region_id']}
                    for f in ('observed_at', 'collected_at'):
                        item[f] = stamp(item[f])
                    for f in ('avg_speed_kmh', 'congestion_index'):
                        item[f] = format(item[f], '.2f')
                    for f in ('dataset_version', 'batch_id'):
                        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', item[f]):
                            raise ValueError('unsupported TSV identity')
                    records.append(item)
                batches.append({k: batch[k] for k in ('batch_id', 'source_sha256', 'file_sha256', 'dataset_id', 'dataset_version', 'source_type', 'accepted_count')})
        connection.commit()
    finally:
        connection.close()
    if not records:
        raise ValueError('empty warehouse snapshot')
    with (output / 'ods.tsv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        for row in records:
            writer.writerow(['\\N' if row[f] is None else row[f] for f in FIELDS])
    write_json(output / 'observations.json', records)
    manifest = {'contract': 's6-v1', 'sql_sha256': sha(ROOT / 'bigdata/sql/warehouse.hql'),
                'from': start, 'to': end, 'captured_at': stamp(datetime.now(timezone.utc)),
                'ods_sha256': sha(output / 'ods.tsv'), 'observations_sha256': sha(output / 'observations.json'),
                'ods_count': len(records), 'unique_count': len({r['observation_id'] for r in records}), 'batches': batches}
    write_json(output / 'manifest.json', manifest)
    return manifest


def oracle(bundle):
    """Python implementation does not execute or emulate Hive SQL."""
    bundle = Path(bundle)
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    if sha(bundle / 'ods.tsv') != manifest['ods_sha256'] or sha(bundle / 'observations.json') != manifest['observations_sha256']:
        raise ValueError('snapshot checksum mismatch')
    unique = {}
    for row in json.loads((bundle / 'observations.json').read_text(encoding='utf-8')):
        key = tuple(row[f] for f in ('dataset_id', 'target_type', 'target_id', 'observed_at'))
        content = {k: v for k, v in row.items() if k not in ('batch_id', 'source_sha256')}
        if key in unique and unique[key] != content:
            raise ValueError('conflicting duplicate observation')
        unique[key] = content
    grouped = {}
    for row in unique.values():
        for grain, bucket in [('WINDOW', manifest['from']), ('DAY', row['observed_at'][:10] + 'T00:00:00.000Z'),
                              ('HOUR', row['observed_at'][:13] + ':00:00.000Z')]:
            key = tuple(row[f] for f in ADS_FIELDS[:7]) + (grain, bucket)
            group = grouped.setdefault(key, [])
            group.append(row)
    result = []
    for key, rows in grouped.items():
        speed = sum((Decimal(r['avg_speed_kmh']) for r in rows), Decimal(0))
        congestion = sum((Decimal(r['congestion_index']) for r in rows), Decimal(0))
        result.append(dict(zip(ADS_FIELDS, [*key, str(len(rows)), format(speed, '.2f'), format(congestion, '.2f'),
            format((speed / len(rows)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f'),
            format((congestion / len(rows)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f'),
            min(r['observed_at'] for r in rows), max(r['observed_at'] for r in rows)])))
    return sorted(result, key=lambda r: tuple('' if r[f] is None else r[f] for f in ADS_FIELDS[:9]))


def read_ads(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        rows = list(csv.reader(stream, delimiter='\t'))
    if any(len(r) != len(ADS_FIELDS) for r in rows):
        raise ValueError('invalid ADS export shape')
    result = []
    for row in rows:
        item = dict(zip(ADS_FIELDS, [None if v == '\\N' else v for v in row]))
        for f in ('speed_sum', 'congestion_sum', 'avg_speed_kmh', 'congestion_index'):
            value = Decimal(item[f])
            if not value.is_finite() or value.as_tuple().exponent < -2:
                raise ValueError('invalid ADS decimal precision')
            item[f] = format(value, '.2f')
        result.append(item)
    return sorted(result, key=lambda r: tuple('' if r[f] is None else r[f] for f in ADS_FIELDS[:9]))


def reconcile(bundle, export):
    expected, actual = oracle(bundle), read_ads(export)
    if expected != actual:
        raise ValueError('Hive ADS does not match independent Decimal oracle')
    return actual


def publish(bundle, export, release_id, fail_at=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', release_id):
        raise ValueError('invalid release ID')
    rows = reconcile(bundle, export)
    bundle = Path(bundle)
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    # Hive output file ordering is not stable across physical executions. Bind the
    # release to sorted, typed row content, while retaining original TSV in evidence.
    ads_hash = hashlib.sha256(canonical(rows).encode()).hexdigest()
    identity = hashlib.sha256((sha(bundle / 'manifest.json') + ads_hash).encode()).hexdigest()
    connection = connect()
    locked = False
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT GET_LOCK('s6-publish',10) acquired")
            locked = cur.fetchone()['acquired'] == 1
            if not locked:
                raise ValueError('publisher busy')
            # Verify snapshot's batches still identify committed ETL in the target DB.
            for b in manifest['batches']:
                cur.execute('SELECT status,source_sha256,file_sha256 FROM etl_batch WHERE batch_id=%s', (b['batch_id'],))
                found = cur.fetchone()
                if not found or found != {'status': 'SUCCEEDED', 'source_sha256': b['source_sha256'], 'file_sha256': b['file_sha256']}:
                    raise ValueError('publication target lineage mismatch')
            cur.execute('SELECT * FROM warehouse_release WHERE release_id=%s FOR UPDATE', (release_id,))
            prior = cur.fetchone()
            if prior and prior['content_sha256'] != identity:
                raise ValueError('release identity conflict')
            if prior and prior['status'] == 'PUBLISHED':
                connection.commit()
                return {'release_id': release_id, 'reused': True, 'rows': len(rows), 'sha256': identity}
            cur.execute('SELECT r.captured_at FROM warehouse_current c JOIN warehouse_release r USING(release_id) WHERE c.singleton=1 FOR UPDATE')
            current = cur.fetchone()
            if current and timestamp(manifest['captured_at']) < current['captured_at']:
                raise ValueError('stale snapshot cannot replace a newer release')
            if not prior:
                cur.execute('INSERT INTO warehouse_release (release_id,status,content_sha256,ads_sha256,window_from,window_to,captured_at,manifest,row_count) '
                    "VALUES (%s,'STAGING',%s,%s,%s,%s,%s,%s,%s)",
                    (release_id, identity, ads_hash, timestamp(manifest['from']), timestamp(manifest['to']), timestamp(manifest['captured_at']), canonical(manifest), len(rows)))
            else:
                cur.execute("UPDATE warehouse_release SET status='STAGING',error_code=NULL WHERE release_id=%s", (release_id,))
            connection.commit()
            for index, row in enumerate(rows):
                values = [row[f] for f in ADS_FIELDS]
                for f in ('bucket_start', 'observed_from', 'observed_to'):
                    values[ADS_FIELDS.index(f)] = timestamp(row[f])
                cur.execute('INSERT INTO warehouse_metric (release_id,' + ','.join(ADS_FIELDS) + ') VALUES (' + ','.join(['%s'] * (len(values) + 1)) + ')', [release_id, *values])
                if fail_at == 'insert' and index == 0:
                    raise RuntimeError('injected insert failure')
            cur.execute('SELECT ' + ','.join(ADS_FIELDS) + ' FROM warehouse_metric WHERE release_id=%s', (release_id,))
            stored = cur.fetchall()
            for row in stored:
                for f in ('bucket_start', 'observed_from', 'observed_to'):
                    row[f] = stamp(row[f])
                row['sample_count'] = str(row['sample_count'])
                for f in ('speed_sum', 'congestion_sum', 'avg_speed_kmh', 'congestion_index'):
                    row[f] = format(row[f], '.2f')
            if sorted(stored, key=lambda r: tuple('' if r[f] is None else r[f] for f in ADS_FIELDS[:9])) != rows:
                raise ValueError('MySQL readback reconciliation failed')
            if fail_at == 'switch':
                raise RuntimeError('injected pointer failure')
            cur.execute("UPDATE warehouse_release SET status='PUBLISHED',published_at=UTC_TIMESTAMP(3) WHERE release_id=%s", (release_id,))
            cur.execute('INSERT INTO warehouse_current (singleton,release_id) VALUES (1,%s) ON DUPLICATE KEY UPDATE release_id=%s', (release_id, release_id))
            if fail_at == 'commit':
                raise RuntimeError('injected pre-commit failure')
            connection.commit()
        return {'release_id': release_id, 'reused': False, 'rows': len(rows), 'sha256': identity}
    except BaseException:
        connection.rollback()
        if locked:
            with connection.cursor() as cur:
                cur.execute("UPDATE warehouse_release SET status='FAILED',error_code='publication_failed' WHERE release_id=%s AND status<>'PUBLISHED'", (release_id,))
            connection.commit()
        raise
    finally:
        if locked:
            with connection.cursor() as cur:
                cur.execute("SELECT RELEASE_LOCK('s6-publish')")
            connection.commit()
        connection.close()
