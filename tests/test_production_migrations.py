"""No production credentials; API fixtures and isolated PostgreSQL schemas only."""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('production_migrations', ROOT / 'tools/production_migrations.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
REGISTRY = json.loads((ROOT / '.github/production-migrations.json').read_text())
ITEM = REGISTRY['approvals']['30']
TRUSTED = 'f' * 40


class FakeAPI:
    def __init__(self):
        self.pr = {'state': 'open', 'draft': False, 'merged': False,
            'base': {'ref': 'main', 'repo': {'full_name': m.REPOSITORY}},
            'head': {'sha': ITEM['sha'], 'repo': {'full_name': m.REPOSITORY}}}
        self.comment = {'issue_url': f'https://api.github.com/repos/{m.REPOSITORY}/issues/30',
            'user': {'login': 'chatgpt-codex-connector[bot]'},
            'body': "Codex Review: Didn't find any major issues.\n**Reviewed commit:** `" + ITEM['sha'][:10] + '`'}
        self.reviews = []
        self.runs = [{'id': n, 'workflow_id': n, 'event': 'pull_request', 'head_sha': ITEM['sha'],
            'head_repository': {'full_name': m.REPOSITORY}, 'run_number': 1, 'run_attempt': 1,
            'status': 'completed', 'conclusion': 'success'} for n in range(1, 4)]
        self.jobs = {n: [{'name': name, 'status': 'completed', 'conclusion': 'success'}]
            for n, name in enumerate(m.WORKFLOWS.values(), 1)}

    def get(self, path):
        if path == '/branches/main': return {'commit': {'sha': TRUSTED}}
        if path == '/pulls/30': return self.pr
        if path.startswith('/issues/comments/'): return self.comment
        names = [p.rsplit('/', 1)[1] for p in m.WORKFLOWS]
        return {'id': names.index(path.rsplit('/', 1)[1]) + 1}

    def pages(self, path, key=None):
        if path.endswith('/reviews'): return self.reviews
        if path.startswith('/actions/runs?'): return self.runs
        return self.jobs[int(path.split('/')[3])]


class GateTests(unittest.TestCase):
    def test_only_explicit_immutable_main_approval_accepts_pr(self):
        self.assertEqual(m.approval(REGISTRY, '30'), ITEM)
        for number in ('31', '-1', '30;echo secret', '030', '../30'):
            with self.assertRaises(m.GateError): m.approval(REGISTRY, number)
        bad = deepcopy(REGISTRY);bad['approvals']['30']['path'] = '../../env.py'
        with self.assertRaises(m.GateError): m.approval(bad, '30')

    def test_github_accepts_clean_exact_head_and_rejects_unapproved_variants(self):
        m.validate_github(FakeAPI(), '30', ITEM, TRUSTED)
        mutations = [lambda a: a.pr.update(draft=True), lambda a: a.pr.update(state='closed'),
            lambda a: a.pr['head'].update(sha='e'*40), lambda a: a.pr['head'].update(repo={'full_name':'fork/repo'}),
            lambda a: a.pr['base'].update(ref='untrusted'), lambda a: a.comment['user'].update(login='spoof'),
            lambda a: a.comment.update(body="Didn't find any major issues. **Reviewed commit:** `1111111111`"),
            lambda a: a.comment.update(issue_url='https://api.github.com/repos/other/repo/issues/30'),
            lambda a: a.runs[0].update(status='in_progress'), lambda a: a.runs[0].update(conclusion='failure'),
            lambda a: a.runs[0].update(event='workflow_dispatch'), lambda a: a.jobs[1][0].update(conclusion='skipped'),
            lambda a: a.reviews.append({'state':'CHANGES_REQUESTED','user':{'id':1}})]
        for change in mutations:
            api=FakeAPI();change(api)
            with self.assertRaises(m.GateError): m.validate_github(api,'30',ITEM,TRUSTED)
        with self.assertRaises(m.GateError): m.validate_github(FakeAPI(),'30',ITEM,'e'*40)

    def test_latest_failed_or_pending_run_cannot_reuse_old_success(self):
        for status, conclusion in [('in_progress',None),('completed','failure')]:
            api=FakeAPI();api.runs.append({**api.runs[0],'id':99,'run_number':2,'status':status,'conclusion':conclusion})
            with self.assertRaises(m.GateError): m.validate_github(api,'30',ITEM,TRUSTED)

    def test_metadata_is_inspected_without_executing_top_level_code(self):
        source=b"raise RuntimeError('must not execute')\nrevision='a81c9d37e502'\ndown_revision='b73a16ce9024'\nbranch_labels=None\ndepends_on=None\n"
        self.assertEqual(m.revision_metadata(source)['revision'],ITEM['revision'])
        with self.assertRaises(m.GateError): m.revision_metadata(source+b"revision='changed'\n")

    def test_bundle_rejects_workflow_changes_extra_migrations_old_edits_and_hash_drift(self):
        old='backend/alembic/versions/b73a16ce9024_old.py'
        old_source=b"revision='b73a16ce9024'\ndown_revision=None\nbranch_labels=None\ndepends_on=None\n"
        new=b"revision='a81c9d37e502'\ndown_revision='b73a16ce9024'\nbranch_labels=None\ndepends_on=None\n"
        item={**ITEM,'sha256':hashlib.sha256(new).hexdigest()}
        def check(mode):
            def fake_git(*args):
                paths=[old] if args[3]==TRUSTED else [old,item['path']]+(['backend/alembic/versions/evil.py'] if mode=='extra' else [])
                return '\n'.join(paths).encode()
            def fake_blob(sha,path):
                if path in m.WORKFLOWS: return b'changed' if mode=='workflow' and sha==ITEM['sha'] else b'trusted'
                if path==old: return old_source+b'\n# changed' if mode=='old' and sha==ITEM['sha'] else old_source
                return new+b'\n# changed' if mode=='hash' else new
            with patch.object(m,'git',side_effect=fake_git),patch.object(m,'blob',side_effect=fake_blob):
                return m.migration_bundle(item,TRUSTED)
        self.assertEqual(check('valid'),new)
        for mode in ('workflow','extra','old','hash'):
            with self.assertRaises(m.GateError): check(mode)

    def test_workflow_only_dispatch_main_environment_minimal_permissions_and_scoped_secret(self):
        import yaml
        workflow=yaml.load((ROOT/'.github/workflows/production-migrations.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow['on']),{'workflow_dispatch'})
        self.assertEqual(workflow['permissions'],{})
        self.assertEqual(workflow['concurrency']['cancel-in-progress'],'false')
        self.assertEqual(workflow['jobs']['migrate']['environment'],'production-migrations')
        secret_steps=[]
        for job in workflow['jobs'].values():
            self.assertIn("github.ref == 'refs/heads/main'",job['if'])
            self.assertTrue(all(v=='read' for v in job['permissions'].values()))
            for step in job['steps']:
                if 'uses' in step: self.assertRegex(step['uses'],r'@[a-f0-9]{40}$')
                if 'secrets.' in json.dumps(step): secret_steps.append(step)
        self.assertEqual(len(secret_steps),1)
        self.assertEqual(secret_steps[0]['env']['DATABASE_URL_DIRECT'],'${{ secrets.DATABASE_URL_DIRECT }}')
        self.assertNotIn('GH_TOKEN',secret_steps[0]['env'])

    def test_cli_refuses_non_main_and_redacts_unexpected_service_exceptions(self):
        secret='must-not-appear-in-output'
        environment={'GITHUB_SHA':TRUSTED,'GITHUB_EVENT_NAME':'workflow_dispatch',
            'GITHUB_REF':'refs/heads/main','GITHUB_REPOSITORY':m.REPOSITORY,
            'GITHUB_WORKFLOW_REF':m.REPOSITORY+'/.github/workflows/production-migrations.yml@refs/heads/main',
            'DATABASE_URL_DIRECT':secret}
        def invoke(env):
            output=io.StringIO()
            with patch.dict(os.environ,env,clear=True),patch.object(m,'git',return_value=(TRUSTED+'\n').encode()),\
                patch.object(m,'blob',return_value=json.dumps(REGISTRY).encode()),\
                patch.object(m,'migration_bundle',return_value=b'approved'),\
                patch.object(m,'migrate',side_effect=RuntimeError(secret)) as migration,\
                patch.object(m.sys,'argv',['production_migrations.py','--pr','30','--apply']),\
                redirect_stdout(output),redirect_stderr(output):
                result=m.main()
            self.assertEqual(result,1);self.assertNotIn(secret,output.getvalue())
            return migration.called
        self.assertTrue(invoke(environment))
        self.assertFalse(invoke({**environment,'GITHUB_REF':'refs/heads/untrusted'}))
        self.assertFalse(invoke({**environment,'GITHUB_EVENT_NAME':'pull_request_target'}))


@unittest.skipUnless(os.getenv('RUN_MIGRATION_TESTS')=='true','Disposable PostgreSQL required')
class PostgreSQLTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine,text
        from sqlalchemy.engine import make_url
        self.url=make_url(os.environ['MIGRATION_TEST_DATABASE_URL'])
        m.require(self.url.host in {'localhost','127.0.0.1'},'Tests may use only loopback PostgreSQL.')
        self.engine=create_engine(self.url.set(drivername='postgresql+psycopg'))
        self.schema='migration_test_'+uuid4().hex
        with self.engine.begin() as c:
            c.execute(text(f'CREATE SCHEMA {self.schema}'))
            c.execute(text(f'CREATE TABLE {self.schema}.alembic_version (version_num varchar(32) PRIMARY KEY)'))
            c.execute(text(f"INSERT INTO {self.schema}.alembic_version VALUES ('b73a16ce9024')"))
            c.execute(text(f'CREATE TABLE {self.schema}.facts (id int PRIMARY KEY, note text)'))
            c.execute(text(f"INSERT INTO {self.schema}.facts VALUES (1,'preserve')"))
        self.direct=self.url.update_query_dict({'options':f'-c search_path={self.schema}'}).render_as_string(hide_password=False)
        self.source=b"from alembic import op\nimport sqlalchemy as sa\nrevision='a81c9d37e502'\ndown_revision='b73a16ce9024'\nbranch_labels=None\ndepends_on=None\ndef upgrade():\n    op.add_column('facts',sa.Column('optional',sa.Text(),nullable=True))\n"

    def tearDown(self):
        from sqlalchemy import text
        with self.engine.begin() as c: c.execute(text(f'DROP SCHEMA {self.schema} CASCADE'))
        self.engine.dispose()

    def revision(self):
        from sqlalchemy import text
        with self.engine.connect() as c: return c.scalar(text(f'SELECT version_num FROM {self.schema}.alembic_version'))

    def test_upgrade_exact_revision_and_idempotent_retry_preserve_facts(self):
        from sqlalchemy import text
        self.assertEqual(m.migrate(ITEM,self.source,self.direct),'applied')
        self.assertEqual(m.migrate(ITEM,self.source,self.direct),'already_applied')
        self.assertEqual(self.revision(),ITEM['revision'])
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text(f'SELECT id,note,optional FROM {self.schema}.facts')).one(),(1,'preserve',None))

    def test_wrong_database_revision_stops_before_ddl(self):
        from sqlalchemy import text
        with self.engine.begin() as c: c.execute(text(f"UPDATE {self.schema}.alembic_version SET version_num='unknown'"))
        with self.assertRaises(m.GateError): m.migrate(ITEM,self.source,self.direct)
        self.assertEqual(self.revision(),'unknown')

    def test_second_runner_is_rejected_by_session_advisory_lock(self):
        from sqlalchemy import text
        with self.engine.connect() as c:
            c.execute(text('SELECT pg_advisory_lock(:key)'),{'key':m.ADVISORY_LOCK});c.commit()
            try:
                with self.assertRaises(m.GateError): m.migrate(ITEM,self.source,self.direct)
            finally: c.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':m.ADVISORY_LOCK});c.commit()
        self.assertEqual(self.revision(),ITEM['down_revision'])

    def test_failed_ddl_rolls_back_schema_and_version(self):
        from sqlalchemy import text
        failed=self.source+b"    raise RuntimeError('synthetic failure')\n"
        with self.assertRaises(RuntimeError): m.migrate(ITEM,failed,self.direct)
        self.assertEqual(self.revision(),ITEM['down_revision'])
        with self.engine.connect() as c:
            self.assertFalse(c.scalar(text("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=:schema AND column_name='optional')"),{'schema':self.schema}))

    def test_exact_pr30_migration_preserves_protected_rows_and_enforces_owned_fk(self):
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError
        source=(ROOT/'tests/fixtures/pr30_a81c9d37e502.txt').read_text(encoding='utf-8').encode()
        self.assertEqual(hashlib.sha256(source).hexdigest(),ITEM['sha256'])
        owner,other,topic=[uuid4() for _ in range(3)]
        with self.engine.begin() as c:
            c.execute(text(f'CREATE TABLE {self.schema}.study_topics (user_id uuid NOT NULL, id uuid PRIMARY KEY, UNIQUE(user_id,id))'))
            c.execute(text(f'CREATE TABLE {self.schema}.study_plan_entries (id int PRIMARY KEY, user_id uuid NOT NULL, name text, completed bool, manual bool, fixed bool)'))
            c.execute(text(f'INSERT INTO {self.schema}.study_topics VALUES (:owner,:topic)'),{'owner':owner,'topic':topic})
            for i in range(3):
                c.execute(text(f'INSERT INTO {self.schema}.study_plan_entries VALUES (:id,:owner,:name,:completed,:manual,:fixed)'),
                    {'id':i,'owner':owner,'name':str(i),'completed':i==0,'manual':i==1,'fixed':i==2})
        self.assertEqual(m.migrate(ITEM,source,self.direct),'applied')
        with self.engine.begin() as c:
            rows=c.execute(text(f'SELECT id,name,completed,manual,fixed,topic_id FROM {self.schema}.study_plan_entries ORDER BY id')).all()
            self.assertEqual(rows,[(0,'0',True,False,False,None),(1,'1',False,True,False,None),(2,'2',False,False,True,None)])
            c.execute(text(f'UPDATE {self.schema}.study_plan_entries SET topic_id=:topic WHERE id=0'),{'topic':topic})
        with self.assertRaises(IntegrityError),self.engine.begin() as c:
            c.execute(text(f'INSERT INTO {self.schema}.study_plan_entries (id,user_id,topic_id) VALUES (9,:owner,:topic)'),{'owner':other,'topic':topic})


if __name__=='__main__': unittest.main()
