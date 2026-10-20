import copy
import csv
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_adapter import inspect_file, inspect_zenodo_v6, confirm, convert, utc_time, hash_json
from examples.fixtures import make_long


def approved(path, review):
    proposal = inspect_file(path)
    return confirm(proposal, review, 'synthetic-fixture-owner', proposal['proposalSha256'])


@pytest.mark.parametrize('fmt', ['csv', 'json'])
def test_explicit_confirmed_mapping_units_timezone_and_hashes(tmp_path, fmt):
    path, review = make_long(tmp_path / fmt, days=1, fmt=fmt, unit='mph')
    proposal = inspect_file(path)
    assert not proposal['executable'] and proposal['state'] == 'PROPOSED'
    assert proposal['suggestions']['timestamp'][0]['field'] == 'measured_at'
    cfg = approved(path, review); data = convert(path, cfg)
    assert data['target'] == 'speed' and data['unit'] == 'km/h'
    assert data['rows'][0]['timestamp'] == '2023-12-31T16:00:00.000Z'
    assert data['mapping_sha256'] == cfg['configurationSha256']
    assert data['rows'][0]['value'] > 60
    assert hash_json(data['rows']) == data['normalized_sha256']


@pytest.mark.parametrize('kind', ['no_actor', 'no_ack', 'no_unit', 'wrong_target', 'no_timezone', 'missing_mapping', 'changed_proposal', 'unapproved_real', 'unsupported_version'])
def test_ambiguity_and_no_confirmation_fail_closed(tmp_path, kind):
    path, review = make_long(tmp_path / 'fixture', days=1)
    proposal = inspect_file(path); actor = 'fixture-owner'; ack = proposal['proposalSha256']
    if kind == 'no_actor': actor = ''
    if kind == 'no_ack': ack = ''
    if kind == 'no_unit': review['unit'] = 'unknown'
    if kind == 'wrong_target': review['target'] = 'congestion_index'
    if kind == 'no_timezone': review['timezone'] = ''
    if kind == 'missing_mapping': review['mapping'].pop('value')
    if kind == 'changed_proposal': proposal['file']['sha256'] = 'a' * 64
    if kind == 'unsupported_version': review['preprocessing_version'] = '999'
    if kind == 'unapproved_real':
        review.update(source_type='historical_snapshot', license_status='unverified')
        cfg = confirm(proposal, review, actor, ack)
        with pytest.raises(ValueError, match='rights/use'): convert(path, cfg)
    else:
        with pytest.raises(ValueError): confirm(proposal, review, actor, ack)


def test_proposal_is_not_an_executable_configuration(tmp_path):
    path, _ = make_long(tmp_path / 'fixture', days=1)
    with pytest.raises(ValueError, match='confirmed'): convert(path, inspect_file(path))


def test_changed_source_after_confirmation_rejected(tmp_path):
    path, review = make_long(tmp_path / 'fixture', days=1)
    cfg = approved(path, review)
    with path.open('a', encoding='utf-8') as stream: stream.write('\n')
    with pytest.raises(ValueError, match='file changed'): convert(path, cfg)


@pytest.mark.parametrize('local', ['2024-11-03 01:30:00', '2024-03-10 02:30:00'])
def test_dst_ambiguous_or_nonexistent_time_is_not_guessed(local):
    with pytest.raises(ValueError, match='ambiguous/nonexistent'): utc_time(local, 'America/Los_Angeles', None)


def test_explicit_timestamp_format_milliseconds_and_offsets():
    assert utc_time('10/20/2024 08:00:00', 'Asia/Shanghai', '%m/%d/%Y %H:%M:%S') == '2024-10-20T00:00:00.000Z'
    assert utc_time('2024-10-20T08:00:00.123+08:00', 'UTC', None) == '2024-10-20T00:00:00.123Z'
    with pytest.raises(ValueError): utc_time('2024-10-20T00:00:00.1234Z', 'UTC', None)


@pytest.mark.parametrize('name,count', [('METR-LA.csv', 207), ('PEMS-BAY.csv', 325)])
def test_selected_zenodo_v6_layout_with_synthetic_fixture_only(tmp_path, name, count):
    path = tmp_path / name
    fields = [''] + [str(700000 + i) for i in range(count)]
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream); writer.writerow(fields)
        writer.writerow(['2024-01-01 00:00:00'] + [40] * count)
        writer.writerow(['2024-01-01 00:05:00'] + [41] * count)
    inspection = inspect_zenodo_v6(path, name)
    assert inspection['sensorColumns'] == count and inspection['integrity'] == 'FAILED'
    assert inspection['status'] == 'NOT_EVALUABLE'  # synthetic rows are not the real distribution.
    _, review = make_long(tmp_path / 'review', days=1)
    review.update(adapter='zenodo-5724362-csv-v6', frequency_seconds=300,
        mapping=dict(timestamp='', sensors=[fields[1], fields[-1]], distribution_file=name))
    data = convert(path, approved(path, review))
    assert len(data['rows']) == 4 and data['source_type'] == 'synthetic_test'
    review.update(target='congestion_index', unit='index_0_10')
    with pytest.raises(ValueError, match='cannot become congestion'): approved(path, review)


def test_pems_user_export_and_distinct_flow_target(tmp_path):
    path = tmp_path / 'station-export.csv'
    path.write_text('Timestamp,Station,AvgSpeed,TotalFlow\n01/01/2024 00:00:00,400001,40,25\n', encoding='utf-8')
    _, review = make_long(tmp_path / 'review', days=1)
    review.update(adapter='pems-user-export-csv-v1', mapping=dict(timestamp='Timestamp', entity='Station', value='TotalFlow'),
        target='flow', unit='vehicles/interval', time_format='%m/%d/%Y %H:%M:%S', frequency_seconds=300)
    data = convert(path, approved(path, review))
    assert data['target'] == 'flow' and data['unit'] == 'vehicles/interval' and data['rows'][0]['value'] == 25


def test_duplicate_conflict_missing_and_zero_policy(tmp_path):
    path = tmp_path / 'rows.json'
    row = dict(measured_at='2024-01-01T00:00:00Z', sensor='s', velocity=0)
    path.write_text(json.dumps([row, row, dict(row, measured_at='2024-01-01T01:00:00Z', velocity=None)]), encoding='utf-8')
    _, review = make_long(tmp_path / 'review', days=1, fmt='json')
    review['zero_policy'] = 'missing'
    data = convert(path, approved(path, review))
    assert data['duplicates'] == 1 and all(r['value'] is None for r in data['rows'])
    path.write_text(json.dumps([row, dict(row, velocity=1)]), encoding='utf-8')
    with pytest.raises(ValueError, match='conflicting duplicate'): convert(path, approved(path, review))


def test_profile_numeric_ambiguity_and_malformed_csv(tmp_path):
    path = tmp_path / 'unknown.csv'; path.write_text('t,a,b\n2024-01-01,1,2\n2024-01-02,3\n', encoding='utf-8')
    proposal = inspect_file(path)
    assert len(proposal['suggestions']['value']) == 2 and proposal['invalidRows'] == 1
    assert 'unit' in proposal['uncertainties']


def test_cli_requires_explicit_synthetic_assertion_outside_controlled_storage(tmp_path):
    path, _ = make_long(tmp_path / 'fixture', days=1)
    cli = Path(__file__).resolve().parents[1] / 'data_cli.py'
    output = tmp_path / 'forbidden.json'
    result = subprocess.run([sys.executable, str(cli), 'inspect', '--input', str(path), '--output', str(output)], capture_output=True)
    assert result.returncode == 1 and not output.exists()


@pytest.mark.parametrize('content', ['[{"value":1,"value":2}]', '[{"value":NaN}]'])
def test_ambiguous_or_nonfinite_json_is_rejected(tmp_path, content):
    path = tmp_path / 'bad.json'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError): inspect_file(path)


def test_nonnumeric_measurement_is_refused(tmp_path):
    path, review = make_long(tmp_path / 'fixture', days=1)
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    columns = lines[1].split(','); columns[-1] = 'unknown'
    lines[1] = ','.join(columns)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    with pytest.raises(ValueError, match='nonnumeric measurement'): convert(path, approved(path, review))
