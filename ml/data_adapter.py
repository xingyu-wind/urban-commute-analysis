"""V3.2 explicit CSV/JSON adaptation. Inspection never approves semantics or rights.

Independent SENSOR/ROAD/CITY target contract: no fake congestion index for speed.
Reuses S5's UTC parser, canonical serialization and identifiers; never writes to
S5 traffic_observation or S6 warehouse_current for a speed-only research task.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data-pipeline'))
from commute_etl.clean import canonical, identifier, timestamp as s5_timestamp

ADAPTER_VERSION = 'traffic-adapter-v1'
MISSING = ('', 'NA', 'NaN', 'null', None)
UNITS = {'speed': {'mph', 'km/h', 'm/s'}, 'flow': {'vehicles/interval', 'vehicles/hour'}, 'congestion_index': {'index_0_10'}}
CANONICAL_UNITS = {'speed': 'km/h', 'congestion_index': 'index_0_10'}
ZENODO = {'METR-LA.csv': (207, 72467662, '7c463fcbd28ecc6c9cd93e1ca120aaaa'),
          'PEMS-BAY.csv': (325, 85718439, 'c8dea58987a5882e946217c22fdb8256')}


def hash_json(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_identity(path):
    sha256, md5, size = hashlib.sha256(), hashlib.md5(), 0
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            sha256.update(chunk); md5.update(chunk); size += len(chunk)
    return dict(sha256=sha256.hexdigest(), md5=md5.hexdigest(), bytes=size)


def read_table(path, fmt=None):
    """Only explicit flat JSON object arrays or headered UTF-8 CSV. No pickle/HDF."""
    path = Path(path)
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('input exceeds explicit 100MiB parser limit')
    fmt = fmt or path.suffix.lower().lstrip('.')
    if fmt == 'csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream)
            try: fields = next(reader)
            except StopIteration: raise ValueError('empty input')
            if len(set(fields)) != len(fields): raise ValueError('duplicate field names')
            for line, row in enumerate(reader, 2):
                yield fields, dict(zip(fields, row)), line, len(row) == len(fields)
    elif fmt == 'json':
        def bad_number(value): raise ValueError('nonfinite JSON literal')
        def unique_object(pairs):
            result = {}
            for key, item in pairs:
                if key in result: raise ValueError('duplicate JSON field names')
                result[key] = item
            return result
        value = json.loads(path.read_text(encoding='utf-8-sig'), parse_constant=bad_number, object_pairs_hook=unique_object)
        if not isinstance(value, list) or not value or not all(isinstance(r, dict) for r in value):
            raise ValueError('expected nonempty flat JSON object array')
        fields = sorted({k for row in value for k in row})
        for i, row in enumerate(value, 1):
            yield fields, row, i, all(not isinstance(v, (dict, list)) for v in row.values())
    else:
        raise ValueError('only CSV/JSON supported; no arbitrary object deserialization')


def inspect_file(path, fmt=None):
    """Full streaming counts plus bounded examples; this report may contain RAW samples.

    Keep external inspection output alongside the controlled ignored input. Only
    redacted aggregate summaries belong in repository evidence or CI artifacts.
    """
    stats, count, invalid = {}, 0, 0
    for fields, row, line, valid in read_table(path, fmt):
        count += 1; invalid += not valid
        for field in fields:
            s = stats.setdefault(field, dict(nulls=0, types=Counter(), examples=[], naiveTime=False, offsetTime=False))
            v = row.get(field)
            if v in MISSING:
                s['nulls'] += 1; continue
            if len(s['examples']) < 3 and v not in s['examples']: s['examples'].append(v)
            kind = 'text'
            try:
                if not isinstance(v, bool) and math.isfinite(float(v)): kind = 'number'
            except (ValueError, TypeError): pass
            if isinstance(v, str):
                try:
                    d = datetime.fromisoformat(v.replace('Z', '+00:00'))
                    kind = 'datetime'; s['naiveTime' if d.tzinfo is None else 'offsetTime'] = True
                except ValueError: pass
            s['types'][kind] += 1
    if not count: raise ValueError('empty input')
    columns = [dict(name=k, **v) for k, v in stats.items()]
    candidates = {role: [] for role in ('timestamp', 'value', 'entity')}
    for c in columns:
        name = c['name'].lower()
        if c['types'].get('datetime', 0): candidates['timestamp'].append(dict(field=c['name'], confidence=.9, reason='parseable date/time examples; timezone still requires confirmation'))
        if c['types'].get('number', 0): candidates['value'].append(dict(field=c['name'], confidence=.5, reason='numeric column; metric/unit are unconfirmed'))
        if any(word in name for word in ('sensor', 'station', 'entity', '路段')): candidates['entity'].append(dict(field=c['name'], confidence=.7, reason='identity-like name; spatial role unconfirmed'))
    report = dict(state='PROPOSED', adapterVersion=ADAPTER_VERSION, file=file_identity(path),
        format=fmt or Path(path).suffix.lstrip('.'), rows=count, invalidRows=invalid, columns=columns, suggestions=candidates,
        uncertainties=['target metric', 'unit', 'timezone of naive timestamps', 'sampling frequency', 'zero/missing semantics', 'dataset/domain identity and rights'],
        executable=False)
    report['proposalSha256'] = hash_json(report)
    return report


def inspect_zenodo_v6(path, distribution_file):
    """Verified actual v6 header layout; counts/checksums are distribution metadata.

    We inspect the raw index column and numeric sensor column names. Nothing here
    grants permission, assigns timezone/mph, or converts speed into congestion.
    """
    if distribution_file not in ZENODO: raise ValueError('unsupported selected distribution')
    count, size, md5 = ZENODO[distribution_file]
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        rows = csv.reader(stream)
        fields = next(rows)
        if len(fields) != count + 1 or fields[0] != '' or len(set(fields)) != len(fields) or not all(re.fullmatch(r'\d+', f) for f in fields[1:]):
            raise ValueError('not the selected Zenodo v6 index/sensor CSV layout')
        n = bad = missing = zeros = 0; first = last = None; previous = None; irregular = 0
        for row in rows:
            n += 1
            if len(row) != len(fields): bad += 1
            try: d = datetime.fromisoformat(row[0])
            except (ValueError, IndexError): bad += 1; continue
            if d.tzinfo is not None: raise ValueError('unexpected timestamp version; re-review mapping')
            if previous is not None and (d - previous).total_seconds() != 300: irregular += 1
            previous = d; first = first or row[0]; last = row[0]
            for v in row[1:]:
                if v in MISSING: missing += 1
                else:
                    try:
                        value = float(v)
                        if not math.isfinite(value) or value < 0: bad += 1
                        zeros += value == 0
                    except ValueError: bad += 1
    actual = file_identity(path)
    complete = actual['bytes'] == size and actual['md5'] == md5
    return dict(adapter='zenodo-5724362-csv-v6', distributionFile=distribution_file, record='5724362', version='v6',
        file=actual, expected=dict(bytes=size, md5=md5), integrity='VERIFIED' if complete else 'FAILED',
        sensorColumns=count, observedRows=n, invalidRowsOrValues=bad, missingCells=missing, zeroCells=zeros,
        observedNaiveFrom=first, observedNaiveTo=last, irregularIntervals=irregular, observedFrequencySeconds=300 if not irregular else None,
        timezone=None, unit=None, target='speed_candidate_unconfirmed', fullDistributionCoverageVerified=complete,
        status='NOT_EVALUABLE', reasons=['user has not approved real training', 'unit/timezone/zero semantics and upstream rights not confirmed']
            + ([] if complete else ['transfer incomplete or differs from distribution size/MD5; no full-series claim']))


def confirm(proposal, review, actor, acknowledgement):
    """Explicit human CLI action. An automatic recommendation is never executable."""
    proposed = {k: v for k, v in proposal.items() if k != 'proposalSha256'}
    if proposal.get('state') != 'PROPOSED' or proposal.get('executable') is not False or proposal.get('proposalSha256') != hash_json(proposed):
        raise ValueError('changed or invalid proposal')
    if not actor.strip() or acknowledgement != proposal['proposalSha256']:
        raise ValueError('explicit actor and exact proposal acknowledgement required')
    required = {'mapping_version', 'preprocessing_version', 'adapter', 'mapping', 'dataset_id', 'dataset_version', 'domain_id', 'city_id',
        'source_type', 'source_url', 'license_status', 'license_evidence', 'allowed_uses', 'timezone', 'time_format',
        'target', 'unit', 'frequency_seconds', 'spatial_grain', 'zero_policy'}
    if set(review) != required: raise ValueError('explicit complete review required; no inferred defaults')
    if review['mapping_version'] != '1' or review['preprocessing_version'] != '1': raise ValueError('unsupported mapping/preprocessing version')
    if review['time_format'] is not None and not isinstance(review['time_format'], str): raise ValueError('explicit timestamp format or null required')
    for k in ('dataset_id', 'domain_id', 'city_id'): identifier(review[k])
    if review['target'] not in UNITS or review['unit'] not in UNITS[review['target']]: raise ValueError('metric/unit ambiguity')
    if review['spatial_grain'] not in ('CITY', 'REGION', 'ROAD', 'SENSOR') or review['zero_policy'] not in ('valid', 'missing'):
        raise ValueError('unconfirmed spatial/missing semantics')
    if review['source_type'] not in ('synthetic_test', 'historical_snapshot') or review['license_status'] not in ('not_applicable', 'verified', 'unverified', 'restricted'):
        raise ValueError('unsupported source/licensing status')
    if review['source_type'] == 'synthetic_test' and review['license_status'] != 'not_applicable': raise ValueError('synthetic license mismatch')
    if not isinstance(review['allowed_uses'], list) or not all(isinstance(v, str) for v in review['allowed_uses']): raise ValueError('allowed uses required')
    if not all(isinstance(review[k], str) and review[k].strip() for k in ('dataset_version', 'mapping_version', 'preprocessing_version', 'source_url', 'license_evidence', 'timezone')):
        raise ValueError('unconfirmed version/source/timezone')
    try: ZoneInfo(review['timezone'])
    except KeyError as error: raise ValueError('unknown timezone; no implicit UTC assumption') from error
    if type(review['frequency_seconds']) is not int or review['frequency_seconds'] <= 0: raise ValueError('sampling frequency required')
    mapping = review['mapping']; fields = {v['name'] for v in proposal['columns']}
    if review['adapter'] in ('long-csv-v1', 'long-json-v1', 'pems-user-export-csv-v1'):
        if set(mapping) != {'timestamp', 'value', 'entity'} or not set(mapping.values()) <= fields or len(set(mapping.values())) != 3:
            raise ValueError('ambiguous/missing long-table field mapping')
    elif review['adapter'] == 'zenodo-5724362-csv-v6':
        if set(mapping) != {'timestamp', 'sensors', 'distribution_file'} or mapping['distribution_file'] not in ZENODO:
            raise ValueError('selected Zenodo layout/version required')
        if mapping['timestamp'] != '' or not isinstance(mapping['sensors'], list) or not mapping['sensors'] or not set(mapping['sensors']) <= fields - {''}:
            raise ValueError('explicit sensor selection required')
        if review['target'] != 'speed' or review['spatial_grain'] != 'SENSOR': raise ValueError('sensor speed cannot become congestion')
    else: raise ValueError('unsupported explicit adapter')
    result = dict(state='CONFIRMED', adapterVersion=ADAPTER_VERSION, file=proposal['file'], review=review,
                  confirmation=dict(actor=actor, proposalSha256=proposal['proposalSha256'], confirmedAt=datetime.now(timezone.utc).isoformat()))
    result['configurationSha256'] = hash_json(result)
    return result


def utc_time(value, zone, fmt):
    d = datetime.strptime(value, fmt) if fmt else datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None:
        tz = ZoneInfo(zone)
        candidates = [d.replace(tzinfo=tz, fold=i) for i in (0, 1)]
        valid = [v for v in candidates if v.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) == d]
        if not valid or len({v.utcoffset() for v in valid}) != 1: raise ValueError('ambiguous/nonexistent local time; explicit offset required')
        d = valid[0]
    if d.microsecond % 1000: raise ValueError('submillisecond precision requires an explicit policy')
    return s5_timestamp(d.astimezone(timezone.utc).isoformat(timespec='milliseconds'), None)


def convert(path, config):
    if config.get('state') != 'CONFIRMED' or config.get('adapterVersion') != ADAPTER_VERSION or config.get('configurationSha256') != hash_json({k: v for k, v in config.items() if k != 'configurationSha256'}):
        raise ValueError('only an intact confirmed mapping is executable')
    if file_identity(path) != config['file']: raise ValueError('source file changed after user confirmation')
    r = config['review']; mapping = r['mapping']
    if r['source_type'] != 'synthetic_test' and (r['license_status'] != 'verified' or 'analysis' not in r['allowed_uses']):
        raise ValueError('real-source rights/use not approved')
    if r['adapter'] == 'zenodo-5724362-csv-v6':
        inspection = inspect_zenodo_v6(path, mapping['distribution_file'])
        if r['source_type'] != 'synthetic_test' and inspection['integrity'] != 'VERIFIED': raise ValueError('incomplete selected distribution')
    rows, seen, duplicates = [], {}, 0
    fmt = 'json' if r['adapter'] == 'long-json-v1' else 'csv'
    for fields, row, line, valid in read_table(path, fmt):
        if not valid: raise ValueError('invalid row width/nested JSON at record ' + str(line))
        t = utc_time(row[mapping['timestamp']], r['timezone'], r['time_format'])
        entities = mapping['sensors'] if 'sensors' in mapping else [str(row[mapping['entity']])]
        for entity in entities:
            raw = row.get(entity) if 'sensors' in mapping else row.get(mapping['value'])
            if raw in MISSING: value = None
            else:
                if isinstance(raw, bool): raise ValueError('boolean is not a measurement')
                try: value = Decimal(str(raw))
                except InvalidOperation as error: raise ValueError('nonnumeric measurement') from error
                if not value.is_finite() or value < 0: raise ValueError('invalid measurement')
                if value == 0 and r['zero_policy'] == 'missing': value = None
                elif r['target'] == 'speed':
                    value *= {'mph': Decimal('1.609344'), 'm/s': Decimal('3.6'), 'km/h': Decimal(1)}[r['unit']]
                    if value > 250: raise ValueError('speed outside supported km/h range')
                elif r['target'] == 'congestion_index' and value > 10: raise ValueError('index outside 0-10')
                if value is not None: value = float(value)
            key = (entity, t)
            if key in seen:
                if seen[key] != value: raise ValueError('conflicting duplicate observation')
                duplicates += 1; continue
            if not entity or len(entity) > 128: raise ValueError('invalid entity identity')
            seen[key] = value
            rows.append(dict(entity_id=entity, timestamp=t, value=value))
    rows.sort(key=lambda v: (v['entity_id'], v['timestamp']))
    return dict(contract='traffic-series-v1', dataset_id=r['dataset_id'], dataset_version=r['dataset_version'],
        domain_id=r['domain_id'], city_id=r['city_id'], source_type=r['source_type'], source_url=r['source_url'],
        license_status=r['license_status'], license_evidence=r['license_evidence'], allowed_uses=r['allowed_uses'],
        target=r['target'], unit=CANONICAL_UNITS.get(r['target'], r['unit']), original_unit=r['unit'], timezone=r['timezone'],
        frequency_seconds=r['frequency_seconds'], spatial_grain=r['spatial_grain'], mapping_version=r['mapping_version'],
        preprocessing_version=r['preprocessing_version'], mapping_sha256=config['configurationSha256'],
        source_sha256=config['file']['sha256'], normalized_sha256=hash_json(rows), duplicates=duplicates,
        missing_policy='preserve missing labels; causal feature fill only in evaluator', rows=rows)
