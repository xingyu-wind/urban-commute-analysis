"""Validate every captured Java traffic response against the complete OpenAPI schemas."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'contracts'))
from validate_contract import load_contract, body_errors, error_summary

directory = Path(sys.argv[1])
manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
if manifest['exitCode'] != 0 or not manifest['noRequestMocking'] or manifest['pageErrors']:
    raise ValueError('S4 browser driver failed')
spec, registry, checker = load_contract()
seen = set()
for capture in manifest['responses']:
    body = json.loads((directory / capture['file']).read_text(encoding='utf-8'))
    errors = body_errors(spec, registry, checker, capture['path'], str(capture['status']), body)
    if errors:
        raise ValueError('Invalid actual response: ' + error_summary(errors))
    if body['meta']['requestId'] != capture['requestId']:
        raise ValueError('Request ID mismatch')
    seen.add((capture['path'], capture['status']))
for endpoint in ('summary', 'series', 'regions', 'roads'):
    if ('/api/v1/traffic/' + endpoint, 200) not in seen:
        raise ValueError('Missing real traffic endpoint capture: ' + endpoint)
if not any(status == 400 for _, status in seen):
    raise ValueError('Missing actual invalid request')
print(json.dumps({'actualResponsesValidated': len(manifest['responses']), 'endpointStatusCoverage': sorted(seen)}, indent=2))
