"""Single-session dataset lock + atomic observations/lineage/success transition.

An interrupted transaction rolls back. RUNNING is only reclaimed while holding the
same dataset lock, so a live owner cannot be mistaken for a crashed process.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
import os
import re

import pymysql

from .clean import OUTPUT_FIELDS, canonical


def connect():
    url = os.environ.get('TEST_DB_URL', '')
    match = re.fullmatch(r'jdbc:mysql://127\.0\.0\.1:(\d+)/(s3test_[0-9a-f]{32})\?connectionTimeZone=UTC', url)
    user = os.environ.get('TEST_DB_USER', '')
    if not match or not re.fullmatch(r's3t_[0-9a-f]{20}', user):
        raise ValueError('Refusing non-isolated ETL database; use scripts/s3_database.py')
    connection = pymysql.connect(host='127.0.0.1', port=int(match[1]), database=match[2],
        user=user, password=os.environ['TEST_DB_PASSWORD'], charset='utf8mb4',
        autocommit=False, connect_timeout=10, read_timeout=60, write_timeout=60,
        cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() db, SUBSTRING_INDEX(CURRENT_USER(),'@',1) user, @@server_uuid uuid, VERSION() version")
            actual = cursor.fetchone()
            if (actual['db'] != os.environ['TEST_DB_SCHEMA'] or actual['db'] != match[2]
                    or actual['user'] != user or actual['uuid'] != os.environ['TEST_DB_SERVER_UUID']
                    or not actual['version'].startswith('8.4.')):
                raise ValueError('Actual MySQL ETL test identity mismatch')
            cursor.execute("SET time_zone='+00:00'")
        connection.commit()
        return connection
    except BaseException:
        connection.close()
        raise


def ensure_row(cursor, table, key, values):
    """Identifiers are internal constants; all caller values are bound parameters."""
    columns = list(values)
    cursor.execute(f"SELECT {','.join(columns)} FROM {table} WHERE {key}=%s FOR UPDATE", (values[key],))
    existing = cursor.fetchone()
    if existing is None:
        cursor.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))})", tuple(values.values()))
    else:
        for field, expected in values.items():
            actual = existing[field]
            if isinstance(actual, Decimal) and expected is not None:
                expected = Decimal(str(expected))
            if actual != expected:
                raise ValueError('catalog_conflict:' + table + ':' + field)


def catalog(cursor, c, source_hash, manifest):
    ensure_row(cursor, 'dataset_registry', 'dataset_id', c['dataset'])
    for city in c['catalog']['cities']:
        cursor.execute('SELECT id FROM city WHERE id=%s FOR UPDATE', (city['id'],))
        if cursor.fetchone():
            # A stable city can host observations from several independently filtered datasets.
            ensure_row(cursor, 'city', 'id', city)
        else:
            ensure_row(cursor, 'city', 'id', {**city, 'dataset_id': c['dataset']['dataset_id']})
    for region in c['catalog']['regions']:
        ensure_row(cursor, 'region', 'id', {**dict.fromkeys(('center_lat', 'center_lon', 'coordinate_system')), **region})
    for road in c['catalog']['roads']:
        ensure_row(cursor, 'road_segment', 'id', {'region_id': None, **road})
    # Hash is of the complete parser/configuration snapshot, not an external permission certificate.
    cursor.execute('SELECT manifest FROM etl_source WHERE source_sha256=%s', (source_hash,))
    existing = cursor.fetchone()
    if existing:
        if json.loads(existing['manifest']) != manifest:
            raise ValueError('source_hash_conflict')
    else:
        cursor.execute('INSERT INTO etl_source (source_sha256,dataset_id,manifest) VALUES (%s,%s,%s)',
                       (source_hash, c['dataset']['dataset_id'], canonical(manifest)))


def db_values(row):
    values = []
    for field in OUTPUT_FIELDS:
        value = row[field]
        if field in ('observed_at', 'collected_at'):
            value = datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
        if field in ('avg_speed_kmh', 'congestion_index'):
            value = Decimal(value)
        values.append(value)
    return tuple(values)


def load(connection, c, rows, report, manifest, batch_id, file_name, after_insert=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', batch_id):
        raise ValueError('invalid_batch_id')
    import hashlib
    lock = 's5:' + hashlib.sha256(c['dataset']['dataset_id'].encode()).hexdigest()[:60]
    with connection.cursor() as cursor:
        cursor.execute('SELECT GET_LOCK(%s,10) acquired', (lock,))
        if cursor.fetchone()['acquired'] != 1:
            raise ValueError('dataset_busy')
    started = False
    conflicts = 0
    conflict_details = []
    try:
        with connection.cursor() as cursor:
            catalog(cursor, c, report['source_sha256'], manifest)
            cursor.execute('SELECT * FROM etl_batch WHERE batch_id=%s FOR UPDATE', (batch_id,))
            prior = cursor.fetchone()
            if prior:
                if prior['source_sha256'] != report['source_sha256'] or prior['file_sha256'] != report['file_sha256']:
                    raise ValueError('batch_identity_conflict')
                if prior['status'] == 'SUCCEEDED':
                    connection.commit()
                    return batch_result(connection, batch_id, reused=True)
                cursor.execute("UPDATE etl_batch SET status='RUNNING',attempts=attempts+1,started_at=UTC_TIMESTAMP(3),"
                               'finished_at=NULL,error_code=NULL,written_count=0,existing_count=0,conflict_count=0,conflict_details=NULL WHERE batch_id=%s', (batch_id,))
            else:
                cursor.execute('INSERT INTO etl_batch (batch_id,source_sha256,file_sha256,file_name,status,input_count,accepted_count,rejected_count,duplicate_count) '
                               "VALUES (%s,%s,%s,%s,'RUNNING',%s,%s,%s,%s)",
                               (batch_id, report['source_sha256'], report['file_sha256'], file_name[:255],
                                report['input_count'], report['accepted_count'], report['rejected_count'], report['duplicate_count']))
                cursor.executemany('INSERT INTO etl_rejection (batch_id,record_number,reason,raw_record) VALUES (%s,%s,%s,%s)',
                    [(batch_id, r['row_number'], r['reason'], json.dumps(r['raw_record'], ensure_ascii=False, allow_nan=False)) for r in report['rejections']])
            connection.commit()  # Durable RUNNING and quality evidence before writing observations.
            started = True
            written = existing = 0
            for row in rows:
                values = db_values(row)
                cursor.execute('SELECT id,' + ','.join(OUTPUT_FIELDS) + ' FROM traffic_observation '
                               'WHERE dataset_id=%s AND target_type=%s AND target_id=%s AND observed_at=%s FOR UPDATE',
                               (row['dataset_id'], row['target_type'], row['target_id'], values[6]))
                prior_row = cursor.fetchone()
                if prior_row:
                    if tuple(prior_row[f] for f in OUTPUT_FIELDS) != values:
                        conflicts += 1
                        conflict_details.append({'key': {k: row[k] for k in ('dataset_id', 'target_type', 'target_id', 'observed_at')},
                            'different_fields': [f for f, value in zip(OUTPUT_FIELDS, values) if prior_row[f] != value]})
                        continue
                    ident = prior_row['id']
                    disposition = 'EXISTING'
                    existing += 1
                else:
                    cursor.execute('INSERT INTO traffic_observation (' + ','.join(OUTPUT_FIELDS) + ') VALUES (' + ','.join(['%s'] * len(values)) + ')', values)
                    ident = cursor.lastrowid
                    disposition = 'WRITTEN'
                    written += 1
                    if after_insert:
                        after_insert(written)
                cursor.execute('INSERT INTO etl_batch_observation (batch_id,observation_id,disposition) VALUES (%s,%s,%s)',
                               (batch_id, ident, disposition))
            if conflicts:
                raise ValueError('observation_content_conflict')
            cursor.execute("UPDATE etl_batch SET status='SUCCEEDED',written_count=%s,existing_count=%s,"
                           'finished_at=UTC_TIMESTAMP(3) WHERE batch_id=%s', (written, existing, batch_id))
            connection.commit()  # Observations, lineage and final counts commit together.
        return batch_result(connection, batch_id)
    except BaseException as error:
        connection.rollback()
        if started:
            # A broken connection leaves RUNNING. A later lock owner can safely retry it.
            try:
                with connection.cursor() as cursor:
                    code = 'observation_content_conflict' if conflicts else 'transaction_failed'
                    cursor.execute("UPDATE etl_batch SET status='FAILED',written_count=0,existing_count=0,conflict_count=%s,conflict_details=%s,"
                                   'error_code=%s,finished_at=UTC_TIMESTAMP(3) WHERE batch_id=%s', (conflicts, canonical(conflict_details), code, batch_id))
                connection.commit()
            except pymysql.MySQLError:
                pass
        raise error
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT RELEASE_LOCK(%s)', (lock,))
            connection.commit()
        except pymysql.MySQLError:
            pass


def batch_result(connection, batch_id, reused=False):
    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM etl_batch WHERE batch_id=%s', (batch_id,))
        result = cursor.fetchone()
    connection.commit()
    if result and result['conflict_details'] is not None:
        result['conflict_details'] = json.loads(result['conflict_details'])
    return {**{k: v.isoformat() + 'Z' if isinstance(v, datetime) else v for k, v in (result or {}).items()}, 'reused': reused}
