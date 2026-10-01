import os
import json
import asyncio
import unittest
from types import SimpleNamespace
from uuid import UUID
from datetime import date
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.studies import StudyProgram,StudyTopic,StudySchedule,StudySession,StudyTarget
from db.models.identity import User
from services import edital_analyses as analyses
import test_postgres_runtime_catalog as catalog_tests
import test_postgres_runtime_editais as edital_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeEditalImport(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        self.area=self.ok(await self.http.get('/api/study/areas'))[1]['area_id']
        self.doc=edital_tests.RuntimeEditais.document(self)
        self.doc['cargos'][0]['disciplinas'][0].update(peso=2,peso_status='explicito',peso_fonte='página 1',num_questoes=10)
        await analyses.save(self.uid,self.doc)
        self.weekly=[{'dia':'Segunda','blocos':[{'disciplina':'Português','duracao_minutos':60}]}]
        self.llm=AsyncMock(return_value=json.dumps({'cronograma_semanal':self.weekly,'estrategia':{'resumo':'Estudar'}}))
        async def authenticate(authorization=None,session_token=None):
            return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.patches=[patch('services.edital_import_routes.get_current_user',authenticate),patch('services.edital_import_routes.call_llm',self.llm),
            patch('services.study_schedule_routes.account',account),patch('services.study_activity_routes.account',account)]
        for p in self.patches: p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def import_program(self,key='import-edital-once',headers=None):
        return await self.http.post('/api/study/programs/import-edital-with-cargo',json={
            'area_id':self.area,'analysis_id':self.doc['analysis_id'],'cargo_index':0,'hours_per_day':2,'days_per_week':4},
            headers={'Idempotency-Key':key,**(headers or {})})

    async def test_import_replay_normalized_rows_schedule_and_verticalization(self):
        responses=await asyncio.gather(*(self.import_program() for _ in range(4)))
        results=[self.ok(r) for r in responses]; pid=results[0]['program']['program_id']; nid=results[0]['disciplinas'][0]['notebook_id']
        self.assertEqual(len({r['program']['program_id'] for r in results}),1)
        async with unit_of_work() as session:
            for model in (StudyProgram,StudyTopic,StudySchedule,StudyTarget):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,25)
            session.add(StudySession(user_id=self.uid,notebook_id=UUID(nid),date=date.today(),duration_minutes=60,completed=True))
        base='/api/study/programs/'+pid
        vertical=self.ok(await self.http.get(base+'/edital-verticalizado'))
        self.assertEqual(vertical['total_disciplinas'],1); self.assertEqual(vertical['disciplinas'][0]['peso_fonte'],'página 1')
        timetable=self.ok(await self.http.get(base+'/cronograma'))
        self.assertEqual(timetable['cronograma'][0]['total_minutes'],60)
        self.assertEqual(timetable['program']['source_type'],'edital_import')
        indicator=self.ok(await self.http.get(base+'/study-indicators'))['indicators'][0]
        self.assertEqual(indicator['total_study_minutes'],60)
        self.assertEqual(indicator['study_hours'],1)
        self.assertEqual((await self.http.get(base+'/edital-verticalizado',headers={'Authorization':'Bearer bob'})).status_code,404)

    async def test_invalid_ai_schedule_rolls_back_program_topics_and_xp(self):
        self.llm.return_value=json.dumps({'cronograma_semanal':[{'dia':'Segunda','blocos':[{'disciplina':'Português','duracao_minutos':999}]}]})
        self.assertEqual((await self.import_program()).status_code,422)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyProgram).where(StudyProgram.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_direct_pdf_import_uses_same_atomic_writer(self):
        parsed={'concurso':{'nome':'Concurso','cargo':'Analista'},'disciplinas':self.doc['cargos'][0]['disciplinas'],
            'cronograma_semanal':self.weekly,'estrategia':{}}
        with patch('services.edital_import_routes.get_user_api_key',AsyncMock(return_value='test-key')), \
             patch('services.edital_import_routes.extract_pdf_text',return_value='Conteúdo do edital'), \
             patch('services.edital_import_routes.call_gemini',AsyncMock(return_value=(json.dumps(parsed),None))):
            result=self.ok(await self.http.post('/api/study/programs/import-edital',data={'area_id':self.area,'hours_per_day':'2','days_per_week':'4'},
                files={'file':('edital.pdf',b'%PDF-test','application/pdf')},headers={'Idempotency-Key':'direct-pdf-import'}))
        self.assertEqual(result['schedules_created'],1)
        self.assertEqual(result['program']['edital_data']['pdf_filename'],'edital.pdf')

    async def test_owner_validation_precedes_ai_and_schedule_mutations(self):
        self.assertEqual((await self.import_program(headers={'Authorization':'Bearer bob'})).status_code,404)
        self.llm.assert_not_awaited()
        result=self.ok(await self.import_program()); pid=result['program']['program_id']; nid=result['disciplinas'][0]['notebook_id']
        base='/api/study/programs/'+pid
        body={'disciplinas':[{'notebook_id':nid,'weight':3,'user_difficulty':'alta'}],'regenerate_schedule':True,'hours_per_day':1,'days_per_week':3}
        updated=self.ok(await self.http.post(base+'/update-disciplinas',json=body))
        self.assertEqual(updated['schedules_regenerated'],3)
        self.assertEqual((await self.http.post(base+'/update-disciplinas',json=body,headers={'Authorization':'Bearer bob'})).status_code,404)
        rows=self.ok(await self.http.get('/api/study/schedule')); self.assertEqual(len(rows),3)
        self.assertEqual(self.ok(await self.http.get('/api/study/schedule',headers={'Authorization':'Bearer bob'})),[])
        self.assertEqual((await self.http.delete('/api/study/schedule/'+rows[0]['schedule_id'],headers={'Authorization':'Bearer bob'})).status_code,404)
        self.ok(await self.http.delete('/api/study/schedule/'+rows[0]['schedule_id']))
        self.assertEqual(len(self.ok(await self.http.get('/api/study/schedule'))),2)
