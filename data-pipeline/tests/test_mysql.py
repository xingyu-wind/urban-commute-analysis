"""Real MySQL only; every write guarded by the existing S3 identity environment."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from commute_etl.clean import clean
from commute_etl.store import batch_result, connect, load

pytestmark = [pytest.mark.mysql, pytest.mark.skipif(not os.environ.get('TEST_DB_URL'), reason='run via s3_database.py')]
EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def bundle(fmt='csv', suffix=''):
    c = json.loads((EXAMPLES / (fmt + '-config.json')).read_text(encoding='utf-8'))
    if suffix:
        c['dataset']['dataset_id'] += '-' + suffix
        # Each test owns independent dimensions, no shared destructive fixture cleanup.
        for group in c['catalog'].values():
            for item in group:
                for key in ('id', 'city_id', 'region_id'):
                    if item.get(key): item[key] += '-' + suffix
    raw = (EXAMPLES / ('traffic.' + fmt)).read_bytes()
    if suffix:
        # Replace identifiers using decoded structures, avoiding repeated substring substitutions.
        original = json.loads((EXAMPLES / (fmt + '-config.json')).read_text(encoding='utf-8'))
        mapping = {item['id']: item['id'] + '-' + suffix for group in original['catalog'].values() for item in group}
        raw = (EXAMPLES / ('traffic.' + fmt)).read_bytes()
        import re
        text = raw.decode()
        text = re.sub(r's5-[a-z-]+', lambda m: mapping.get(m[0], m[0]), text)
        raw = text.encode()
    return c, *clean(raw, c)


@pytest.fixture
def db():
    connection = connect()
    yield connection
    connection.close()


def query(db, sql, values=()):
    with db.cursor() as cursor:
        cursor.execute(sql, values)
        result = cursor.fetchall()
    db.commit()
    return result


def perform(db, bundle, batch, hook=None):
    c, rows, report, manifest = bundle
    return load(db, c, rows, report, manifest, batch, 'traffic.' + c['format'], hook)


def test_first_repeat_new_batch_json_and_reconciliation(db):
    data = bundle(suffix='normal')
    result = perform(db, data, 'first')
    assert (result['input_count'], result['accepted_count'], result['rejected_count'], result['duplicate_count'], result['written_count']) == (16, 9, 6, 1, 9)
    repeat = perform(db, data, 'first')
    assert repeat['reused'] and repeat['attempts'] == 1
    repeat = perform(db, data, 'repeat')
    assert repeat['written_count'] == 0 and repeat['existing_count'] == 9
    result = perform(db, bundle('json', 'normal'), 'json')
    assert (result['written_count'], result['existing_count']) == (1, 9)
    counts = query(db, "SELECT COUNT(*) n FROM traffic_observation WHERE dataset_id='s5-synthetic-v1-normal'")[0]
    assert counts['n'] == 10
    assert query(db, "SELECT COUNT(*) n FROM etl_rejection WHERE batch_id='first'")[0]['n'] == 6
    lineage = query(db, "SELECT disposition,COUNT(*) n FROM etl_batch_observation WHERE batch_id='json' GROUP BY disposition")
    assert {r['disposition']: r['n'] for r in lineage} == {'WRITTEN': 1, 'EXISTING': 9}
    # Independent SQL oracle, with hand calculated expected values, not production API SQL.
    actual = query(db, "SELECT COUNT(*) n,SUM(avg_speed_kmh)/COUNT(*) speed,SUM(congestion_index)/COUNT(*) congestion "
                       "FROM traffic_observation WHERE dataset_id='s5-synthetic-v1-normal' AND target_type='CITY' AND city_id='s5-city-normal'")[0]
    assert actual == {'n': 3, 'speed': 40, 'congestion': 5}


def test_conflict_rolls_back_new_rows_and_is_reported(db):
    data = bundle('json', 'conflict')
    # Load original first nine; next transaction inserts a new row BEFORE conflicting content.
    first = deepcopy(data); first[1].pop(); first[2].update(input_count=9, accepted_count=9)
    perform(db, first, 'conflict-base')
    c, rows, report, manifest = deepcopy(data)
    rows[0]['avg_speed_kmh'] = '37.00'
    rows = [rows[-1], *rows[:-1]]
    with pytest.raises(ValueError, match='observation_content_conflict'):
        load(db, c, rows, report, manifest, 'conflict', 'conflict.json')
    batch = batch_result(db, 'conflict')
    assert (batch['status'], batch['conflict_count'], batch['written_count']) == ('FAILED', 1, 0)
    assert batch['conflict_details'][0]['different_fields'] == ['avg_speed_kmh']
    assert query(db, "SELECT COUNT(*) n FROM traffic_observation WHERE dataset_id='s5-synthetic-v1-conflict'")[0]['n'] == 9
    assert query(db, "SELECT avg_speed_kmh speed FROM traffic_observation WHERE dataset_id='s5-synthetic-v1-conflict' AND target_type='CITY' AND target_id='s5-city-conflict' ORDER BY observed_at LIMIT 1")[0]['speed'] == 36
    assert query(db, "SELECT COUNT(*) n FROM etl_batch_observation WHERE batch_id='conflict'")[0]['n'] == 0
    with pytest.raises(ValueError, match='batch_identity_conflict'):
        perform(db, bundle('csv', 'conflict'), 'conflict')


def test_mid_transaction_exception_then_retry(db):
    data = bundle(suffix='retry')
    def fail(_): raise RuntimeError('injected test failure')
    with pytest.raises(RuntimeError): perform(db, data, 'retry', fail)
    assert batch_result(db, 'retry')['status'] == 'FAILED'
    assert query(db, "SELECT COUNT(*) n FROM traffic_observation WHERE dataset_id='s5-synthetic-v1-retry'")[0]['n'] == 0
    result = perform(db, data, 'retry')
    assert result['status'] == 'SUCCEEDED' and result['attempts'] == 2 and result['written_count'] == 9


def test_process_crash_leaves_running_and_safe_recovery(db):
    # A true process exit closes the socket without executing Python exception/finally handlers.
    program = "from tests.test_mysql import bundle,perform; from commute_etl.store import connect; import os; perform(connect(),bundle(suffix='crash'),'crash',lambda _: os._exit(73))"
    env = {**os.environ, 'PYTHONPATH': str(EXAMPLES.parent)}
    result = subprocess.run([sys.executable, '-c', program], cwd=EXAMPLES.parent, env=env)
    assert result.returncode == 73
    assert batch_result(db, 'crash')['status'] == 'RUNNING'
    assert query(db, "SELECT COUNT(*) n FROM traffic_observation WHERE dataset_id='s5-synthetic-v1-crash'")[0]['n'] == 0
    result = perform(db, bundle(suffix='crash'), 'crash')
    assert (result['status'], result['attempts'], result['written_count']) == ('SUCCEEDED', 2, 9)


def test_lock_prevents_reclaim_of_live_owner(db):
    import hashlib
    c, *_ = bundle(suffix='locked')
    lock = 's5:' + hashlib.sha256(c['dataset']['dataset_id'].encode()).hexdigest()[:60]
    owner = connect()
    try:
        query(owner, 'SELECT GET_LOCK(%s,0) acquired', (lock,))
        with pytest.raises(ValueError, match='dataset_busy'):
            perform(db, bundle(suffix='locked'), 'locked')
        assert query(db, "SELECT COUNT(*) n FROM etl_batch WHERE batch_id='locked'")[0]['n'] == 0
    finally:
        query(owner, 'SELECT RELEASE_LOCK(%s)', (lock,)); owner.close()


def test_guard_checks_actual_identity_before_write(monkeypatch):
    monkeypatch.setenv('TEST_DB_SERVER_UUID', 'wrong-server')
    with pytest.raises(ValueError, match='identity mismatch'): connect()


def test_cli_csv_json_outputs_match_database(db, tmp_path):
    env = {**os.environ, 'PYTHONPATH': str(EXAMPLES.parent)}
    for fmt in ('csv', 'json'):
        output = tmp_path / fmt
        result = subprocess.run([sys.executable, '-m', 'commute_etl', '--config', str(EXAMPLES / (fmt + '-config.json')),
            '--input', str(EXAMPLES / ('traffic.' + fmt)), '--batch', 'cli-' + fmt, '--output', str(output), '--load'], env=env)
        assert result.returncode == 0
        batch = json.loads((output / 'batch.json').read_text())
        report = json.loads((output / 'quality.json').read_text())
        for key in ('input_count', 'accepted_count', 'rejected_count', 'duplicate_count', 'file_sha256', 'source_sha256'):
            assert batch[key] == report[key]
        assert len(json.loads((output / 'normalized.json').read_text())) == batch['accepted_count']
        assert len(json.loads((output / 'rejections.json').read_text())) == batch['rejected_count']
    assert query(db, "SELECT COUNT(*) n FROM traffic_observation WHERE dataset_id='s5-synthetic-v1'")[0]['n'] == 10
