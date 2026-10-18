"""Validate actual browser -> Vite -> Java payloads using the WP2 OpenAPI schemas."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'contracts'))
from validate_contract import body_errors, error_summary, load_contract

directory = Path(sys.argv[1])
manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
spec, registry, checker = load_contract()
accepted = []
transport = []
java_logs = '\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in directory.glob('java-*.log'))
for response in manifest['responses']:
    if response['source'] == 'vite-proxy-transport-failure':
        transport.append({'index': response['index'], 'status': response['status'], 'note': 'Vite infrastructure error, not a Java OpenAPI error envelope'})
        continue
    assert response['status'] == 200, response
    body = json.loads((directory / response['bodyFile']).read_text(encoding='utf-8'))
    errors = body_errors(spec, registry, checker, response['contractPath'], str(response['status']), body)
    assert not errors, error_summary(errors)
    request_id = response['headers']['x-request-id']
    assert request_id in java_logs, 'Browser response must correlate to an actual Java request log'
    if 'meta' in body:
        assert body['meta']['requestId'] == request_id
    accepted.append({'index': response['index'], 'path': response['contractPath'], 'phase': response['phase'], 'requestId': request_id, 'schemaValidation': 'PASS', 'javaLogCorrelation': 'PASS'})
assert {row['path'] for row in accepted} == {'/health', '/api/v1/cities'}
assert transport, 'Backend-stop test must capture actual proxy failure'
result = {'exitCode': 0, 'javaResponsesAccepted': accepted, 'infrastructureFailures': transport, 'note': 'Real captured browser responses; no mock success payloads'}
(directory / 'schema-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'CAPTURED_OPENAPI_VALIDATION=PASS; JAVA_RESPONSES={len(accepted)}; PROXY_FAILURES={len(transport)}; JAVA_LOG_CORRELATION=PASS')
