"""Original redistributable synthetic series; never accesses external data or network."""
import csv
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import random


def make_long(output, domain='alpha', days=14, frequency=3600, fmt='csv', unit='km/h'):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    start = datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=8)))
    count = days * 86400 // frequency
    rand = random.Random(20261020 + sum(map(ord, domain)))
    rows = []
    shift = 0 if domain == 'alpha' else 13
    for i in range(count):
        t = start + timedelta(seconds=i * frequency)
        value = 40 + shift + 7 * math.sin(i * frequency * 2 * math.pi / 86400) + rand.uniform(-.3, .3)
        rows.append(dict(measured_at=t.isoformat(), sensor='synthetic-sensor', velocity=round(value, 4)))
    path = output / ('traffic.' + fmt)
    if fmt == 'csv':
        with path.open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    else: path.write_text(json.dumps(rows), encoding='utf-8')
    review = dict(mapping_version='1', preprocessing_version='1', adapter='long-' + fmt + '-v1',
        mapping=dict(timestamp='measured_at', entity='sensor', value='velocity'), dataset_id=domain + '-synthetic-v1',
        dataset_version='1', domain_id=domain, city_id=domain, source_type='synthetic_test',
        source_url='generated-fixture://ml/examples/fixtures.py', license_status='not_applicable',
        license_evidence='original deterministic synthetic test observations; no real traffic', allowed_uses=['analysis'],
        timezone='Asia/Shanghai', time_format=None, target='speed', unit=unit, frequency_seconds=frequency,
        spatial_grain='SENSOR', zero_policy='valid')
    (output / 'review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
    return path, review
