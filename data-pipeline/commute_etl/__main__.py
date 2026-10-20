"""python -m commute_etl --config config.json --input file.csv --batch id --output new-dir [--load]"""
import argparse
import csv
import json
from pathlib import Path
import sys

from .clean import OUTPUT_FIELDS, clean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--load', action='store_true')
    args = parser.parse_args()
    # Never replace an earlier report or unmanaged output.
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        config = json.loads(args.config.read_text(encoding='utf-8-sig'))
        rows, report, manifest = clean(args.input.read_bytes(), config)
        for name, value in (('normalized.json', rows), ('quality.json', report), ('source.json', manifest),
                            ('rejections.json', report['rejections'])):
            (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        with (args.output / 'normalized.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        if args.load:
            from .store import batch_result, connect, load
            connection = connect()
            try:
                try:
                    batch = load(connection, config, rows, report, manifest, args.batch, args.input.name)
                except Exception:
                    batch = batch_result(connection, args.batch)
                    (args.output / 'batch.json').write_text(json.dumps(batch, indent=2) + '\n', encoding='utf-8')
                    raise
                (args.output / 'batch.json').write_text(json.dumps(batch, indent=2) + '\n', encoding='utf-8')
            finally:
                connection.close()
        print(json.dumps({k: v for k, v in report.items() if k not in ('rejections', 'duplicates')}))
        return 0
    except Exception as error:
        # SQL/server diagnostics may contain secrets or input. Persist only classified errors.
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        (args.output / 'failure.json').write_text(json.dumps({'status': 'FAILED', 'reason': reason}) + '\n', encoding='utf-8')
        print('ETL failed; inspect failure.json and batch.json', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
