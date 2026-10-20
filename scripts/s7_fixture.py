"""Deterministic synthetic_test input for the REAL S5 admission/ETL path."""
from datetime import datetime, timedelta, timezone
import json
import hashlib
import math
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
START = '2023-10-23T00:00:00.000Z'
CUTOFF = '2026-10-19T00:00:00.000Z'


def generate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads((ROOT / 'data-pipeline/examples/json-config.json').read_text(encoding='utf-8'))
    config['dataset'].update(dataset_id='s7-synthetic-v1', dataset_version='1',
        source_name='S7 seeded multi-season congestion demo', description='1092 UTC days; synthetic_test only; seed 20261020; not real traffic accuracy.')
    config['source'].update(url='scripts/s7_fixture.py', time_coverage=[START, CUTOFF],
        name='S7 repository-owned seeded fixture generator', field_dictionary=dict(config['fields']),
        generator_config=dict(seed=20261020, days=1092, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        granularity='CITY; four 6h slots per UTC day with deterministic irregular minutes',
        coordinate_system='not_applicable; no coordinates')
    config['catalog'] = dict(cities=[dict(id='s7-city', name='S7 合成预测城市'), dict(id='s7-empty', name='S7 无模型城市')], regions=[], roads=[])
    randomizer = random.Random(20261020)
    start = datetime(2023, 10, 23, tzinfo=timezone.utc)
    rows = []
    for i in range(1092):
        day = start + timedelta(days=i)
        center = 4.4 + (0.85 if day.weekday() < 5 else -1.0) + .7 * math.sin(2 * math.pi * i / 365.2425) + .18 * math.sin(2 * math.pi * i / 28)
        for hour in (0, 6, 12, 18):
            observed = day + timedelta(hours=hour, minutes=randomizer.randrange(1, 45))
            value = round(center + randomizer.gauss(0, .2) + (.25 if hour in (6, 18) else -.25), 2)
            rows.append(dict(city_id='s7-city', target_type='CITY', target_id='s7-city',
                observed_at=observed.isoformat().replace('+00:00', 'Z'),
                collected_at=(observed + timedelta(minutes=1)).isoformat().replace('+00:00', 'Z'),
                velocity=round(65 - 4 * value, 2), index=value))
    (output / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'traffic.json').write_text(json.dumps(rows, ensure_ascii=False) + '\n', encoding='utf-8')
    return output
