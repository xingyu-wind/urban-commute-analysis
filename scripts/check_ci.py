"""Check this project's CI security, platform and execution policy (not a cloud run)."""
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / '.github/workflows/s2-ci.yml'
# BaseLoader preserves the GitHub keyword 'on' instead of YAML 1.1's boolean True.
workflow = yaml.load(path.read_text(encoding='utf-8'), Loader=yaml.BaseLoader)


def require(condition, message):
    if not condition:
        raise ValueError(message)


require(set(workflow['on']) == {'pull_request', 'push', 'workflow_dispatch'}, 'Unexpected workflow trigger')
require(workflow['on']['pull_request']['branches'] == ['main'], 'PRs must target main')
require('main' in workflow['on']['push']['branches'], 'Missing main push regression')
require(workflow['permissions'] == {'contents': 'read'}, 'Only read-only source permission is allowed')
job = workflow['jobs']['regression']
require(job['runs-on'] == 'ubuntu-24.04', 'Unexpected runner')
require('permissions' not in job, 'Job must not override read-only permissions')
mysql = job.get('services', {}).get('mysql', {})
require(mysql.get('image') == 'mysql:8.4', 'S3 requires real MySQL 8.4')
require('DB_URL' not in job.get('env', {}), 'Integration tests must not inherit a persistent datasource')
steps = job['steps']
actions = {}
for step in steps:
    require('continue-on-error' not in step, 'Tests must not silently continue on error')
    if 'uses' in step:
        action, sha = step['uses'].rsplit('@', 1)
        require(action.startswith('actions/') and re.fullmatch(r'[0-9a-f]{40}', sha), 'Action must use an official full commit SHA')
        actions[action] = step.get('with', {})
    if 'working-directory' in step:
        require((ROOT / step['working-directory']).is_dir(), 'Invalid working-directory')
require(actions['actions/checkout']['persist-credentials'] == 'false', 'Checkout credentials must not persist')
require(actions['actions/setup-java']['java-version'] == '21', 'Java must match local major 21')
require(actions['actions/setup-node']['node-version'].startswith('24.'), 'Node must match local major 24')
for action in ('actions/setup-java', 'actions/setup-node', 'actions/setup-python'):
    require((ROOT / actions[action]['cache-dependency-path']).is_file(), 'Invalid dependency cache path')
commands = '\n'.join(step.get('run', '') for step in steps)
require('s3_database.py --probe-isolation' in commands, 'Missing pre-migration isolation rejection evidence')
require('s3-repeat.json' in commands, 'Missing repeated suite with a fresh schema')
require('--with-restore-target' in commands and '--release-checks' in commands, 'Missing S9 real isolated restore and deployment checks')
warehouse = yaml.load((ROOT / '.github/workflows/s6-warehouse.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
warehouse_commands = '\n'.join(step.get('run','') for step in warehouse['jobs']['warehouse']['steps'])
require('scripts/s6_checks.py --release-checks' in warehouse_commands and '--with-restore-target' in warehouse_commands,
        'Missing S9 restore of actual Hive publication')
for command in ('bash backend/mvnw', 'npm ci', 'npm run type-check', 'npm test', 'npm run build',
                'contracts/validate_contract.py', 'backend/scripts/verify_http.py', 'test:e2e', 'check-regression-failures.py', 'scripts/s4_checks.py',
                'data-pipeline/requirements.lock.txt', 'scripts/s5_checks.py', 'ml/requirements.lock.txt', 'scripts/s7_checks.py', 'scripts/s7_data_checks.py', 'scripts/s8_checks.py'):
    require(command in commands, 'Missing regression command: ' + command)
require('mvnw.cmd' not in commands and 'powershell.exe' not in commands, 'Windows-only entry in Linux CI')
require(not re.search(r'\|\|\s*true|continue-on-error|secrets\.|pull_request_target|write-all', path.read_text(encoding='utf-8')), 'Unsafe failure handling or credentials')
print('CI_POLICY=PASS; triggers, SHA pins, contents:read, Java21/Node24, dependency paths and Linux commands checked')
