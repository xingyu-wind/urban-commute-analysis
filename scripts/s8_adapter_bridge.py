"""Fixed local S8 worker protocol. No command, path or actor comes from browser input.

Invoked by Java with an allowlisted action and server-generated private paths.
stdout/stderr are never copied into responses or evidence. Raw files stay private.
"""
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ml'))
from data_adapter import inspect_file, confirm, convert, read_table
from domain_evaluation import suitability


def execute(request):
    action = request['action']
    raw = Path(request['file'])
    if action == 'inspect':
        if raw.suffix == '.csv':
            with raw.open(encoding='utf-8-sig', newline='') as stream:
                rows = csv.reader(stream, strict=True)
                fields = next(rows)
                if not 3 <= len(fields) <= 400 or any(not f or len(f) > 128 for f in fields):
                    raise ValueError('invalid headers')
                count = 0
                for row in rows:
                    count += 1
                    if len(row) != len(fields): raise ValueError('invalid row width')
                if not count: raise ValueError('no records')
        count = 0
        for fields, row, _, valid in read_table(raw):
            count += 1
            if not valid or len(fields) > 400 or any(not k or len(k) > 128 for k in fields):
                raise ValueError('invalid table')
            if count > 20000: raise ValueError('row limit')
        if not count: raise ValueError('no records')
        return inspect_file(raw)
    if action == 'confirm':
        return confirm(request['proposal'], request['review'], request['actor'], request['acknowledgement'])
    if action == 'import':
        data = convert(raw, request['configuration'])
        quality = suitability(data)
        # A valid upload is not a waiver of S7 quality/rights/task applicability.
        if quality['status'] == 'NOT_EVALUABLE': raise ValueError('not evaluable')
        dest = Path(request['normalized'])
        with dest.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, allow_nan=False)
        return dict(outputSha256=data['normalized_sha256'], quality=quality)
    raise ValueError('unsupported action')


if __name__ == '__main__':
    try:
        result = dict(ok=True, value=execute(json.load(sys.stdin)))
    except Exception:
        # Never return parser excerpts, external field values, filesystem paths or secrets.
        result = dict(ok=False)
    with Path(sys.argv[1]).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False)
