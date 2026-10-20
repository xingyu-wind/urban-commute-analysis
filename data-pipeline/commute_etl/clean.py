"""Small explicit schema. No inferred units, coordinates, time zones or missing zeros."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import io
import json
import re

from . import VERSION

FIELDS = ('city_id', 'target_type', 'target_id', 'observed_at', 'collected_at',
          'speed', 'congestion')
OUTPUT_FIELDS = ('dataset_id', 'city_id', 'region_id', 'road_segment_id', 'target_type',
                 'target_id', 'observed_at', 'collected_at', 'avg_speed_kmh', 'congestion_index')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', value) or len(value) > 64:
        raise ValueError('invalid_identifier')
    return value


def validate_config(c):
    identifier(c['dataset']['dataset_id'])
    d, source = c['dataset'], c['source']
    if set(d) != {'dataset_id', 'source_name', 'source_type', 'license_status', 'license_url', 'dataset_version', 'description'}:
        raise ValueError('invalid_dataset_fields')
    if d['source_type'] == 'synthetic_test':
        if d['license_status'] != 'not_applicable' or source['admission'] != 'synthetic_test':
            raise ValueError('synthetic_provenance_mismatch')
    elif d['source_type'] in ('historical_snapshot', 'authorized_live'):
        if d['license_status'] != 'authorized' or source['admission'] != 'verified_authorized' or not d.get('license_url'):
            raise ValueError('source_not_admitted')
    else:
        raise ValueError('source_not_admitted')
    for key in ('name', 'url', 'license_evidence', 'checked_at', 'time_coverage',
                'granularity', 'field_dictionary', 'time_information', 'coordinate_system'):
        if not source.get(key):
            raise ValueError('missing_source_metadata:' + key)
    coverage = source['time_coverage']
    if not isinstance(coverage, list) or len(coverage) != 2 or timestamp(coverage[0], None) >= timestamp(coverage[1], None):
        raise ValueError('invalid_time_coverage')
    for key, limit in (('source_name', 120), ('dataset_version', 64), ('description', 500)):
        if not isinstance(d[key], str) or not d[key].strip() or len(d[key]) > limit:
            raise ValueError('invalid_dataset_metadata:' + key)
    if d.get('license_url') and len(d['license_url']) > 500:
        raise ValueError('invalid_license_url')
    if c['format'] not in ('csv', 'json') or set(c['fields']) != set(FIELDS):
        raise ValueError('invalid_input_mapping')
    if len(set(c['fields'].values())) != len(FIELDS):
        raise ValueError('ambiguous_field_mapping')
    if c['speed_unit'] not in ('km/h', 'm/s', 'mph') or c['congestion_unit'] not in ('0-10', '0-100'):
        raise ValueError('unknown_unit')
    if c.get('naive_timezone') not in (None, 'UTC'):
        # Explicit offsets accepted in records; local DST times are never guessed.
        raise ValueError('naive_timezone_must_be_UTC_or_absent')
    cities, regions, roads = {}, {}, {}
    for city in c['catalog']['cities']:
        if set(city) != {'id', 'name'}:
            raise ValueError('invalid_city_fields')
        ident = identifier(city['id'])
        if ident in cities or not isinstance(city['name'], str) or not city['name'].strip() or len(city['name']) > 100:
            raise ValueError('invalid_city_catalog')
        cities[ident] = city
    for region in c['catalog']['regions']:
        if not {'id', 'city_id', 'name'} <= set(region) or set(region) - {'id', 'city_id', 'name', 'center_lat', 'center_lon', 'coordinate_system'}:
            raise ValueError('invalid_region_fields')
        ident = identifier(region['id'])
        if ident in regions or region['city_id'] not in cities or not region['name'].strip() or len(region['name']) > 100:
            raise ValueError('invalid_region_catalog')
        coords = [region.get(k) for k in ('center_lat', 'center_lon', 'coordinate_system')]
        if coords != [None, None, None]:
            lat, lon, crs = coords
            if (isinstance(lat, bool) or isinstance(lon, bool) or not isinstance(lat, (int, float))
                    or not isinstance(lon, (int, float)) or not -90 <= lat <= 90 or not -180 <= lon <= 180 or crs != 'WGS84'):
                raise ValueError('invalid_coordinates')
        regions[ident] = region
    for road in c['catalog']['roads']:
        if not {'id', 'city_id', 'name'} <= set(road) or set(road) - {'id', 'city_id', 'name', 'region_id'}:
            raise ValueError('invalid_road_fields')
        ident = identifier(road['id'])
        if (ident in roads or road['city_id'] not in cities or not road['name'].strip() or len(road['name']) > 160
                or (road.get('region_id') is not None and
                    (road['region_id'] not in regions or regions[road['region_id']]['city_id'] != road['city_id']))):
            raise ValueError('invalid_road_catalog')
        roads[ident] = road
    return cities, regions, roads


def timestamp(value, naive_timezone):
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})?', value):
        raise ValueError('invalid_timestamp')
    if re.search(r'[+-]\d{2}:\d{2}$', value) and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError('invalid_utc_offset')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            if naive_timezone != 'UTC':
                raise ValueError('timezone_required')
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError('invalid_or_ambiguous_time') from error
    if not 2000 <= parsed.year <= 2099:
        raise ValueError('time_out_of_range')
    return parsed.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def number(value, factor, maximum):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('invalid_number')
    try:
        parsed = Decimal(str(value)) * factor
        if not parsed.is_finite() or not 0 <= parsed <= maximum:
            raise ValueError('number_out_of_range')
        return format(parsed.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f')
    except (InvalidOperation, OverflowError) as error:
        raise ValueError('invalid_number') from error


def clean(raw: bytes, c: dict):
    if len(raw) > 100 * 1024 * 1024:
        raise ValueError('file_exceeds_100_MiB_limit')
    cities, regions, roads = validate_config(c)
    text = raw.decode('utf-8-sig')
    if c['format'] == 'csv':
        reader = csv.DictReader(io.StringIO(text), strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not set(c['fields'].values()) <= set(reader.fieldnames):
            raise ValueError('invalid_csv_header')
        records = list(reader)
    else:
        records = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))
        if not isinstance(records, list):
            raise ValueError('json_array_required')
    accepted, rejected, duplicates, seen = [], [], [], {}
    for row_number, raw_row in enumerate(records, 1):
        try:
            if not isinstance(raw_row, dict) or None in raw_row:
                raise ValueError('invalid_record_shape')
            row = {}
            for field, source in c['fields'].items():
                if source not in raw_row or raw_row[source] is None or raw_row[source] == '':
                    raise ValueError('missing_required:' + field)
                row[field] = raw_row[source]
            city, level, target = row['city_id'], row['target_type'], row['target_id']
            if city not in cities or level not in ('CITY', 'REGION', 'ROAD'):
                raise ValueError('invalid_city_or_level')
            catalog = {'CITY': cities, 'REGION': regions, 'ROAD': roads}[level]
            if target not in catalog or (target != city if level == 'CITY' else catalog[target]['city_id'] != city):
                raise ValueError('target_city_mismatch')
            observed = timestamp(row['observed_at'], c.get('naive_timezone'))
            collected = timestamp(row['collected_at'], c.get('naive_timezone'))
            if collected < observed:
                raise ValueError('collection_before_observation')
            start, end = c['source']['time_coverage']
            if not timestamp(start, None) <= observed < timestamp(end, None):
                raise ValueError('outside_declared_coverage')
            speed = number(row['speed'], {'km/h': Decimal(1), 'm/s': Decimal('3.6'), 'mph': Decimal('1.609344')}[c['speed_unit']], 250)
            congestion = number(row['congestion'], Decimal('0.1') if c['congestion_unit'] == '0-100' else Decimal(1), 10)
            normalized = dict(zip(OUTPUT_FIELDS, (c['dataset']['dataset_id'], city,
                target if level == 'REGION' else None, target if level == 'ROAD' else None,
                level, target, observed, collected, speed, congestion)))
            key = (level, target, observed)
            if key in seen:
                if seen[key] != normalized:
                    raise ValueError('conflicting_duplicate_in_file')
                duplicates.append({'row_number': row_number, 'reason': 'identical_duplicate'})
            else:
                seen[key] = normalized
                accepted.append(normalized)
        except (ValueError, TypeError, KeyError) as error:
            reason = str(error) if isinstance(error, ValueError) else 'invalid_field_type'
            rejected.append({'row_number': row_number, 'reason': reason, 'raw_record': raw_row})
    manifest = {'pipeline_version': VERSION, 'configuration': c}
    report = {'file_sha256': digest(raw), 'source_sha256': digest(canonical(manifest).encode()),
              'input_count': len(records), 'accepted_count': len(accepted), 'rejected_count': len(rejected),
              'duplicate_count': len(duplicates), 'rejections': rejected, 'duplicates': duplicates}
    return accepted, report, manifest
