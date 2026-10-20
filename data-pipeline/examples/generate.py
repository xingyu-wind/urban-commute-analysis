"""Reproduce small synthetic fixtures exactly; no real traffic or coordinates."""
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
FIELDS = ['city_id', 'target_type', 'target_id', 'observed_at', 'collected_at', 'speed', 'congestion']


def write(name, obj):
    (ROOT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    config = {
        'format': 'csv', 'fields': {k: k for k in FIELDS}, 'speed_unit': 'm/s', 'congestion_unit': '0-100',
        'dataset': {'dataset_id': 's5-synthetic-v1', 'source_name': 'S5 reproducible synthetic traffic',
                    'source_type': 'synthetic_test', 'license_status': 'not_applicable', 'license_url': None,
                    'dataset_version': '1', 'description': 'Generated test observations; no real traffic collection.'},
        'source': {'admission': 'synthetic_test', 'name': 'Repository-owned synthetic fixture generator',
                   'url': 'data-pipeline/examples/generate.py', 'license_evidence': 'Original deterministic test data; external authorization not applicable.',
                   'checked_at': '2026-10-20', 'time_coverage': ['2026-10-15T00:00:00Z', '2026-10-17T00:00:00Z'],
                   'granularity': 'CITY / REGION / ROAD; irregular samples, not vehicle counts',
                   'field_dictionary': {k: k for k in FIELDS}, 'time_information': 'Explicit ISO8601 offsets; UTC millisecond storage',
                   'coordinate_system': 'WGS84 synthetic region centers; no road geometry'},
        'catalog': {'cities': [{'id': 's5-city', 'name': 'S5 合成城市'}, {'id': 's5-other', 'name': 'S5 另一合成城市'}],
                    'regions': [{'id': 's5-east', 'city_id': 's5-city', 'name': 'S5 合成东区', 'center_lat': 30.1, 'center_lon': 120.1, 'coordinate_system': 'WGS84'},
                                {'id': 's5-other-region', 'city_id': 's5-other', 'name': 'S5 另一合成区域'}],
                    'roads': [{'id': 's5-road', 'city_id': 's5-city', 'region_id': 's5-east', 'name': 'S5 合成路段'},
                              {'id': 's5-other-road', 'city_id': 's5-other', 'region_id': 's5-other-region', 'name': 'S5 另一合成路段'}]}}
    clean = []
    def row(city, level, target, hour, speed, congestion):
        return dict(zip(FIELDS, (city, level, target, f'2026-10-15T{hour+8:02}:00:00+08:00',
                                  f'2026-10-15T{hour:02}:05:00Z', speed, congestion)))
    for level, target, speeds in [('CITY', 's5-city', (10, 20)), ('REGION', 's5-east', (5, 15)), ('ROAD', 's5-road', (2, 8))]:
        for hour, speed, congestion in [(0, speeds[0], 20), (1, speeds[1], 40)]:
            clean.append(row('s5-city', level, target, hour, speed, congestion))
    for level, target in [('CITY', 's5-other'), ('REGION', 's5-other-region'), ('ROAD', 's5-other-road')]:
        clean.append(row('s5-other', level, target, 0, 30, 80))
    dirty = [clean[0].copy(), {**clean[0], 'speed': ''}, {**clean[0], 'speed': -1},
             {**clean[0], 'congestion': 101}, {**clean[0], 'target_type': 'ROAD', 'target_id': 's5-other-road'},
             {**clean[0], 'observed_at': '2026-10-15T08:00:00'}, {**clean[0], 'speed': 11}]
    with (ROOT / 'traffic.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader(); writer.writerows(clean + dirty)
    write('csv-config.json', config)
    # Different mapping/units; the first nine records normalize identically to CSV.
    json_rows = [{**r, 'velocity': round(float(r['speed']) * 3.6, 2), 'index': float(r['congestion']) / 10} for r in clean]
    for r in json_rows:
        del r['speed']; del r['congestion']
    json_rows.append({**json_rows[0], 'observed_at': '2026-10-16T02:00:00-04:00', 'collected_at': '2026-10-16T06:05:00Z', 'velocity': 12, 'index': 9})
    write('traffic.json', json_rows)
    config['format'] = 'json'; config['speed_unit'] = 'km/h'; config['congestion_unit'] = '0-10'
    config['fields']['speed'] = 'velocity'; config['fields']['congestion'] = 'index'
    write('json-config.json', config)
    sys.path.insert(0, str(ROOT.parent))
    from commute_etl.clean import OUTPUT_FIELDS, clean as normalize
    rows, report, manifest = normalize((ROOT / 'traffic.json').read_bytes(), config)
    (ROOT / 'standardized').mkdir(exist_ok=True)
    for name, value in [('normalized.json', rows), ('quality.json', report), ('source.json', manifest), ('rejections.json', report['rejections'])]:
        write('standardized/' + name, value)
    with (ROOT / 'standardized/normalized.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


if __name__ == '__main__':
    main()
