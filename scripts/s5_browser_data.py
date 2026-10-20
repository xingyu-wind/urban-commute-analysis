"""Owned synthetic UI fixture, imported exclusively through the real Python CLI."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data-pipeline'))
from commute_etl.clean import clean
from commute_etl.store import catalog, connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'csv', 'json', 'repeat', 'alternate', 'oracle'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    examples = ROOT / 'data-pipeline/examples'
    if args.action == 'prepare':
        output.mkdir(parents=True, exist_ok=False)
        for fmt in ('csv', 'json'):
            c = json.loads((examples / (fmt + '-config.json')).read_text(encoding='utf-8'))
            mapping = {item['id']: item['id'] + '-ui' for group in c['catalog'].values() for item in group}
            for group in c['catalog'].values():
                for item in group:
                    for key in ('id', 'city_id', 'region_id'):
                        if item.get(key): item[key] = mapping[item[key]]
            c['dataset']['dataset_id'] += '-ui'
            (output / (fmt + '-config.json')).write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8')
            raw = re.sub(r's5-[a-z-]+', lambda m: mapping.get(m[0], m[0]), (examples / ('traffic.' + fmt)).read_text(encoding='utf-8'))
            (output / ('traffic.' + fmt)).write_text(raw, encoding='utf-8')
        # Dimensions only, for a true empty-before-import API/browser baseline.
        rows, report, manifest = clean((output / 'traffic.csv').read_bytes(), c := json.loads((output / 'csv-config.json').read_text(encoding='utf-8')))
        connection = connect()
        try:
            with connection.cursor() as cursor:
                catalog(cursor, c, report['source_sha256'], manifest)
            connection.commit()
        finally:
            connection.close()
    elif args.action == 'oracle':
        connection = connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT target_type,COUNT(*) n,SUM(avg_speed_kmh)/COUNT(*) speed,"
                               "SUM(congestion_index)/COUNT(*) congestion FROM traffic_observation "
                               "WHERE dataset_id='s5-synthetic-v1-ui' AND city_id='s5-city-ui' GROUP BY target_type ORDER BY target_type")
                rows = cursor.fetchall()
            print(json.dumps(rows, default=str))
        finally:
            connection.close()
    else:
        fmt = 'csv' if args.action == 'repeat' else 'json' if args.action == 'alternate' else args.action
        config_path = output / (fmt + '-config.json')
        input_path = output / ('traffic.' + fmt)
        if args.action == 'alternate':
            c = json.loads(config_path.read_text(encoding='utf-8'))
            c['dataset']['dataset_id'] = 's5-synthetic-alternate-ui'
            config_path = output / 'alternate-config.json'
            config_path.write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8')
            records = json.loads(input_path.read_text(encoding='utf-8'))
            for record in records:
                record['velocity'] = 200; record['index'] = 1
            input_path = output / 'alternate.json'
            input_path.write_text(json.dumps(records, ensure_ascii=False), encoding='utf-8')
        # Use -m exactly as a user would, with an isolated child process environment.
        command = [sys.executable, '-m', 'commute_etl', '--config', str(config_path),
                   '--input', str(input_path), '--batch', 'ui-' + args.action,
                   '--output', str(output / args.action), '--load']
        result = subprocess.run(command, cwd=ROOT / 'data-pipeline')
        return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
