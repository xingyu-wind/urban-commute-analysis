"""Owned synthetic edge cases; ETL logic stays in S5, no direct observation SQL."""
import json
from pathlib import Path


def generate(root, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    config = json.loads((root / 'data-pipeline/examples/json-config.json').read_text(encoding='utf-8'))
    config['dataset']['dataset_id'] = 's6-edge-v2'
    config['dataset']['dataset_version'] = '2'
    config['source']['time_coverage'][1] = '2026-10-18T00:00:00Z'
    rows = []
    def row(time, speed, index='3.00', city='s5-city', level='CITY', target=None):
        rows.append({'city_id': city, 'target_type': level, 'target_id': target or city,
                     'observed_at': time, 'collected_at': time, 'velocity': speed, 'index': index})
    # Unequal group sizes; averaging hourly means gives the WRONG daily/window mean.
    row('2026-10-15T00:00:00.000Z', '10.00')
    row('2026-10-15T00:00:00.001Z', '20.00')
    row('2026-10-15T00:59:59.999Z', '30.00')
    row('2026-10-15T01:00:00.000Z', '100.00')
    row('2026-10-15T23:59:59.999Z', '40.00')
    row('2026-10-16T00:00:00.000Z', '50.00')
    # Final boundary excluded by the warehouse window, but committed by ETL.
    row('2026-10-17T00:00:00.000Z', '250.00')
    # Separate cities and levels, validated road->region relation.
    row('2026-10-16T00:00:00.000Z', '200.00', city='s5-other')
    row('2026-10-16T00:00:00.000Z', '60.00', level='REGION', target='s5-east')
    row('2026-10-16T00:00:00.000Z', '70.00', level='ROAD', target='s5-road')
    # Exact half cent final means test ROUND_HALF_UP independently in Hive.
    row('2026-10-16T01:00:00.000Z', '1.00', level='REGION', target='s5-east')
    row('2026-10-16T01:00:00.001Z', '1.01', level='REGION', target='s5-east')
    row('2026-10-16T02:00:00.000Z', None)  # missing metric rejected, never zero
    row('2026-10-16T02:00:00.000Z', '90.00', city='s5-other', level='ROAD', target='s5-road')  # cross-city rejected
    for name, value in [('config.json', config), ('traffic.json', rows)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output
