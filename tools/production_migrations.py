"""Trusted-main production migration gate. Never import the candidate application."""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

REPOSITORY = 'jpedrosampaio/SiriusFrontAndBack'
WORKFLOWS = {
    '.github/workflows/security-tests.yml': 'security-routes',
    '.github/workflows/postgres-tests.yml': 'postgres',
    '.github/workflows/frontend-build.yml': 'build',
}
ADVISORY_LOCK = 731030001
ROOT = Path(__file__).resolve().parents[1]


class GateError(Exception):
    """Only controlled messages; never embed service errors or connection URLs."""


def require(condition, message):
    if not condition:
        raise GateError(message)


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT, stderr=subprocess.DEVNULL)


def blob(sha, path):
    return git('show', f'{sha}:{path}')


def fetch_approved(sha, token):
    # Read-only token is ephemeral process environment, not a command argument or saved Git config.
    environment = {**os.environ, 'GIT_CONFIG_COUNT': '1',
        'GIT_CONFIG_KEY_0': 'http.https://github.com/.extraheader',
        'GIT_CONFIG_VALUE_0': 'AUTHORIZATION: basic ' + base64.b64encode(('x-access-token:' + token).encode()).decode()}
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', sha], cwd=ROOT, env=environment,
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def revision_metadata(source):
    """Inspect literals without importing or executing a migration."""
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            names, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            names, value = [node.target], node.value
        else:
            continue
        for name in names:
            if isinstance(name, ast.Name) and name.id in {'revision', 'down_revision', 'branch_labels', 'depends_on'}:
                require(name.id not in values, 'Duplicate revision metadata.')
                values[name.id] = ast.literal_eval(value)
    require(set(values) == {'revision', 'down_revision', 'branch_labels', 'depends_on'}, 'Missing literal revision metadata.')
    return values


def approval(registry, number):
    require(bool(re.fullmatch(r'[1-9][0-9]{0,8}', str(number))), 'Invalid PR number.')
    require(registry.get('repository') == REPOSITORY, 'Wrong approval repository.')
    item = registry.get('approvals', {}).get(str(number))
    require(isinstance(item, dict), 'PR has no immutable approval in main.')
    require(bool(re.fullmatch(r'[a-f0-9]{40}', item.get('sha', ''))), 'Invalid approved SHA.')
    require(bool(re.fullmatch(r'[a-f0-9]{64}', item.get('sha256', ''))), 'Invalid migration hash.')
    for field in ('revision', 'down_revision'):
        require(bool(re.fullmatch(r'[a-f0-9]{12}', item.get(field, ''))), 'Invalid approved revision.')
    require(bool(re.fullmatch(r'backend/alembic/versions/[a-z0-9_]+\.py', item.get('path', ''))), 'Invalid migration path.')
    require(isinstance(item.get('review_comment_id'), int) and item['review_comment_id'] > 0, 'Missing exact-head review.')
    return item


class GitHub:
    def __init__(self, token):
        require(bool(token), 'Missing read-only GitHub token.')
        self.token = token

    def get(self, path):
        require(path.startswith('/'), 'Invalid API path.')
        request = Request('https://api.github.com/repos/' + REPOSITORY + path,
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28'})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def pages(self, path, key=None):
        rows = []
        for page in range(1, 21):
            value = self.get(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            batch = value[key] if key else value
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise GateError('API pagination bound exceeded; no partial approval.')


def validate_github(api, number, item, trusted_sha):
    require(api.get('/branches/main')['commit']['sha'] == trusted_sha, 'Main changed; dispatch a new run from main.')
    pr = api.get(f'/pulls/{number}')
    require(pr['state'] == 'open' and not pr.get('draft') and not pr.get('merged'), 'PR must be open, ready and unmerged.')
    require(pr['base']['ref'] == 'main' and pr['base']['repo']['full_name'] == REPOSITORY, 'Wrong PR base.')
    require(pr['head']['repo'] is not None and pr['head']['repo']['full_name'] == REPOSITORY, 'Fork PRs are forbidden.')
    require(pr['head']['sha'] == item['sha'], 'PR changed after immutable approval.')
    comment = api.get(f'/issues/comments/{item["review_comment_id"]}')
    require(comment.get('issue_url') == f'https://api.github.com/repos/{REPOSITORY}/issues/{number}', 'Review belongs to another PR.')
    require(comment.get('user', {}).get('login') == 'chatgpt-codex-connector[bot]', 'Review is not from the configured Codex app.')
    text = comment.get('body', '')
    reviewed = re.search(r'\*\*Reviewed commit:\*\* `([a-f0-9]{10,40})`', text)
    require(reviewed is not None and item['sha'].startswith(reviewed.group(1)) and
        "Didn't find any major issues." in text, 'Missing clean exact-head Codex review.')
    reviews = api.pages(f'/pulls/{number}/reviews')
    latest = {}
    for review in reviews:
        if review.get('state') in {'APPROVED', 'CHANGES_REQUESTED'}:
            latest[review['user']['id']] = review
    require(not any(r['state'] == 'CHANGES_REQUESTED' for r in latest.values()), 'Outstanding requested changes.')
    runs = api.pages(f'/actions/runs?head_sha={item["sha"]}', 'workflow_runs')
    for path, job_name in WORKFLOWS.items():
        workflow_id = api.get('/actions/workflows/' + path.rsplit('/', 1)[1])['id']
        matching = [r for r in runs if r['workflow_id'] == workflow_id and r['event'] == 'pull_request'
            and r['head_sha'] == item['sha'] and r.get('head_repository', {}).get('full_name') == REPOSITORY]
        require(bool(matching), 'Required exact-head workflow is missing.')
        run = max(matching, key=lambda r: (r['run_number'], r.get('run_attempt', 1)))
        require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Latest required workflow is not successful.')
        jobs = api.pages(f'/actions/runs/{run["id"]}/jobs?filter=latest', 'jobs')
        require(any(j['name'] == job_name and j['conclusion'] == 'success' for j in jobs), 'Required job was skipped or absent.')
        require(all(j['status'] == 'completed' and j['conclusion'] == 'success' for j in jobs), 'Required workflow has an unsuccessful job.')


def migration_bundle(item, trusted_sha):
    """Read exact Git blobs; candidate env.py, models and requirements never run."""
    for path in WORKFLOWS:
        require(blob(item['sha'], path) == blob(trusted_sha, path), 'Candidate modified a trusted CI workflow.')
    folder = 'backend/alembic/versions/'
    def versions(sha):
        return {p for p in git('ls-tree', '-r', '--name-only', sha, folder).decode().splitlines() if p.endswith('.py')}
    trusted, candidate = versions(trusted_sha), versions(item['sha'])
    require(candidate - trusted == {item['path']} and not trusted - candidate, 'Expected exactly one additive approved migration.')
    metadata = []
    for path in trusted:
        source = blob(trusted_sha, path)
        require(blob(item['sha'], path) == source, 'Existing migration was edited.')
        metadata.append(revision_metadata(source))
    revisions = {m['revision'] for m in metadata}
    parents = {m['down_revision'] for m in metadata if m['down_revision']}
    require(revisions - parents == {item['down_revision']}, 'Main migration head differs from the approved parent.')
    source = blob(item['sha'], item['path'])
    require(hashlib.sha256(source).hexdigest() == item['sha256'], 'Approved migration hash differs.')
    values = revision_metadata(source)
    require(values == {'revision': item['revision'], 'down_revision': item['down_revision'],
        'branch_labels': None, 'depends_on': None}, 'Expected a single linear approved revision.')
    return source


def migrate(item, source, url):
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool
    parsed = make_url(url)
    require(parsed.drivername in {'postgres', 'postgresql', 'postgresql+psycopg'}, 'Only PostgreSQL is supported.')
    require(not (parsed.host or '').endswith('.neon.tech') or (
        '-pooler' not in parsed.host and parsed.query.get('sslmode') in {'require', 'verify-ca', 'verify-full'}),
        'Neon requires a direct TLS URL.')
    engine = create_engine(parsed.set(drivername='postgresql+psycopg'), poolclass=NullPool,
        echo=False, hide_parameters=True, connect_args={'connect_timeout': 15})
    try:
        with engine.connect() as connection:
            require(connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': ADVISORY_LOCK}), 'Another migration holds the database lock.')
            connection.commit()
            try:
                with connection.begin():
                    connection.execute(text("SET LOCAL lock_timeout = '10s'"))
                    connection.execute(text("SET LOCAL statement_timeout = '120s'"))
                    current = MigrationContext.configure(connection).get_current_heads()
                    if current == (item['revision'],):
                        return 'already_applied'
                    require(current == (item['down_revision'],), 'Database revision differs from the approved parent; no migration executed.')
                    with tempfile.TemporaryDirectory(prefix='sirius-approved-migration-') as temporary:
                        directory = Path(temporary)
                        (directory / 'versions').mkdir()
                        (directory / 'versions' / 'anchor.py').write_text(
                            f"revision = {item['down_revision']!r}\ndown_revision = None\n", encoding='utf-8')
                        (directory / 'versions' / 'approved.py').write_bytes(source)
                        # Connection is supplied by trusted main, not by any PR environment code.
                        (directory / 'env.py').write_text(
                            "from alembic import context\n"
                            "context.configure(connection=context.config.attributes['connection'], transactional_ddl=True)\n"
                            "with context.begin_transaction():\n    context.run_migrations()\n", encoding='utf-8')
                        config = Config()
                        config.set_main_option('script_location', str(directory))
                        config.attributes['connection'] = connection
                        command.upgrade(config, item['revision'])
                    require(MigrationContext.configure(connection).get_current_heads() == (item['revision'],), 'Post-migration revision verification failed.')
                return 'applied'
            finally:
                connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': ADVISORY_LOCK})
                connection.commit()
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pr', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        trusted_sha = os.environ.get('GITHUB_SHA', '')
        require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and
            os.environ.get('GITHUB_REF') == 'refs/heads/main' and
            os.environ.get('GITHUB_REPOSITORY') == REPOSITORY and
            os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/production-migrations.yml@refs/heads/main',
            'Only the trusted manual workflow on main may execute.')
        require(bool(re.fullmatch(r'[a-f0-9]{40}', trusted_sha)) and git('rev-parse', 'HEAD').decode().strip() == trusted_sha, 'Trusted checkout does not match workflow SHA.')
        registry = json.loads(blob(trusted_sha, '.github/production-migrations.json'))
        item = approval(registry, args.pr)
        # The apply step receives no API token; validation happened immediately before it.
        if not args.apply:
            validate_github(GitHub(os.environ.get('GH_TOKEN')), args.pr, item, trusted_sha)
            fetch_approved(item['sha'], os.environ['GH_TOKEN'])
        source = migration_bundle(item, trusted_sha)
        print(f"Approved PR #{args.pr}; SHA {item['sha']}; {item['down_revision']} -> {item['revision']}.")
        if args.apply:
            url = os.environ.pop('DATABASE_URL_DIRECT', '')
            require(bool(url), 'Environment DATABASE_URL_DIRECT is missing.')
            result = migrate(item, source, url)
            print(f"Migration result: {result}; revision {item['revision']}.")
    except GateError as error:
        print(f'Migration stopped: {error}', file=sys.stderr)
        return 1
    except Exception:
        print('Migration stopped: validation or execution failed. Credentials and service exceptions are not logged.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
