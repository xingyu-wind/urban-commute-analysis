from copy import deepcopy
import json
from pathlib import Path

import pytest

from commute_etl.clean import clean, number, timestamp, validate_config
from decimal import Decimal

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def fixture():
    return json.loads((EXAMPLES / 'json-config.json').read_text(encoding='utf-8'))


def test_csv_json_and_quality_partition():
    c = json.loads((EXAMPLES / 'csv-config.json').read_text(encoding='utf-8'))
    rows, report, _ = clean((EXAMPLES / 'traffic.csv').read_bytes(), c)
    assert (report['input_count'], report['accepted_count'], report['rejected_count'], report['duplicate_count']) == (16, 9, 6, 1)
    assert rows[0]['observed_at'] == '2026-10-15T00:00:00.000Z'
    assert rows[0]['avg_speed_kmh'] == '36.00'
    assert rows[0]['congestion_index'] == '2.00'
    other, _, _ = clean((EXAMPLES / 'traffic.json').read_bytes(), fixture())
    assert other[:9] == rows
    assert other[-1]['observed_at'] == '2026-10-16T06:00:00.000Z'
    assert {r['reason'] for r in report['rejections']} == {'missing_required:speed', 'number_out_of_range', 'target_city_mismatch', 'invalid_or_ambiguous_time', 'conflicting_duplicate_in_file'}
    committed = json.loads((EXAMPLES / 'standardized/quality.json').read_text(encoding='utf-8'))
    from commute_etl.clean import digest
    assert committed['file_sha256'] == digest((EXAMPLES / 'traffic.json').read_bytes())


@pytest.mark.parametrize('value', ['2026-11-01T01:30:00', '2026-02-30T00:00:00Z', '2026-10-15T00:00:00.0001Z', '1999-12-31T23:00:00Z', '2026-10-15T00:00:00+01:99'])
def test_unsafe_times_rejected(value):
    with pytest.raises(ValueError):
        timestamp(value, None)


def test_explicit_utc_and_mph_rounding():
    assert timestamp('2026-10-15T00:00:00', 'UTC') == '2026-10-15T00:00:00.000Z'
    assert number('60', Decimal('1.609344'), 250) == '96.56'
    assert number('0', Decimal(1), 250) == '0.00'


@pytest.mark.parametrize('value', [None, True, 'NaN', 'Infinity', '-0.01', '250.001', {}, []])
def test_invalid_numbers(value):
    with pytest.raises(ValueError):
        number(value, Decimal(1), 250)


@pytest.mark.parametrize('mutation', ['unit', 'unverified', 'fake_auth', 'coordinates', 'road_city', 'sql_column', 'timezone'])
def test_fail_closed_config(mutation):
    c = deepcopy(fixture())
    if mutation == 'unit': c['speed_unit'] = 'knots'
    if mutation == 'unverified': c['source']['admission'] = 'unverified'
    if mutation == 'fake_auth': c['dataset']['license_status'] = 'authorized'
    if mutation == 'coordinates': c['catalog']['regions'][0]['coordinate_system'] = 'GCJ02'
    if mutation == 'road_city': c['catalog']['roads'][0]['city_id'] = 's5-other'
    if mutation == 'sql_column': c['catalog']['cities'][0]['id) VALUES (1);--'] = 'x'
    if mutation == 'timezone': c['naive_timezone'] = 'America/New_York'
    with pytest.raises(ValueError): validate_config(c)


@pytest.mark.parametrize('patch', [
    {'velocity': None}, {'velocity': True}, {'city_id': []}, {'target_type': 'city'},
    {'target_id': 'missing'}, {'observed_at': '2026-10-17T00:00:00Z'},
    {'collected_at': '2026-10-14T23:59:59Z'}, {'index': -1},
])
def test_rejected_rows_never_become_zero(patch):
    record = json.loads((EXAMPLES / 'traffic.json').read_text())[0]
    rows, report, _ = clean(json.dumps([{**record, **patch}]).encode(), fixture())
    assert rows == []
    assert report['rejected_count'] == 1


def test_malformed_input_fails_file():
    with pytest.raises(ValueError): clean(b'{}', fixture())
    c = fixture(); c['format'] = 'csv'
    with pytest.raises(ValueError): clean(b'a,a\n1,2\n', c)


def test_overwide_csv_row_is_traceably_rejected():
    c = json.loads((EXAMPLES / 'csv-config.json').read_text(encoding='utf-8'))
    raw = (EXAMPLES / 'traffic.csv').read_text(encoding='utf-8').splitlines()
    rows, report, _ = clean((raw[0] + '\n' + raw[1] + ',extra\n').encode(), c)
    assert rows == [] and report['rejections'][0]['reason'] == 'invalid_record_shape'


def test_verified_external_requires_evidence_and_compatible_source_type():
    c = fixture()
    c['dataset'].update(source_type='historical_snapshot', license_status='authorized', license_url='https://example.org/license')
    c['source']['admission'] = 'verified_authorized'
    validate_config(c)
    c['source']['license_evidence'] = ''
    with pytest.raises(ValueError, match='missing_source_metadata'): validate_config(c)
