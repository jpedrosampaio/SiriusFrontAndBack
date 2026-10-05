import os
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from services.time import local_today
import test_postgres_runtime_workout_logs as log_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeMeasurements(unittest.IsolatedAsyncioTestCase):
    ok=log_tests.RuntimeWorkoutLogs.ok
    payload=log_tests.RuntimeWorkoutLogs.payload
    asyncTearDown=log_tests.RuntimeWorkoutLogs.asyncTearDown

    async def asyncSetUp(self):
        await log_tests.RuntimeWorkoutLogs.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        async def authenticate(authorization=None,**kwargs):return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        self.llm=AsyncMock(return_value='Sugestões')
        extra=[patch('services.body_measurements.account',account),patch('services.health_ai_routes.get_current_user',authenticate),patch('services.health_ai_routes.call_llm',self.llm)]
        for p in extra:p.start()
        self.patches.extend(extra)

    async def test_measurements_owner_bmi_period_and_delete(self):
        self.assertIsNone(self.ok(await self.http.get('/api/body-measurements/latest')))
        today=local_today('America/Sao_Paulo'); saved=[]
        for delta,weight in [(400,99),(10,81),(0,80)]:
            saved.append(self.ok(await self.http.post('/api/body-measurements',json={'date':(today-timedelta(days=delta)).isoformat(),'weight_kg':weight,'height_cm':180,'body_fat_percentage':0})))
        self.assertEqual(saved[-1]['bmi'],24.7)
        evolution=self.ok(await self.http.get('/api/body-measurements/evolution',params={'months':1}))
        self.assertEqual(evolution['total_records'],2);self.assertEqual(evolution['changes']['weight_kg'],-1)
        self.assertEqual(evolution['changes']['body_fat_percentage'],0)
        foreign={'Authorization':'Bearer bob'}
        self.assertEqual(self.ok(await self.http.get('/api/body-measurements',headers=foreign)),[])
        url='/api/body-measurements/'+saved[-1]['measurement_id']
        self.assertEqual((await self.http.delete(url,headers=foreign)).status_code,404)
        self.ok(await self.http.delete(url));self.assertEqual(self.ok(await self.http.get('/api/body-measurements/latest'))['weight_kg'],81)
        self.assertEqual((await self.http.post('/api/body-measurements',json={'date':today.isoformat(),'height_cm':0})).status_code,422)

    async def test_suggestions_sql_context_and_saved_insights(self):
        self.assertEqual(self.ok(await self.http.get('/api/body-measurements/recommendations'))['based_on'],'no_data');self.llm.assert_not_awaited()
        self.ok(await self.http.post('/api/workouts',json=self.payload()))
        self.ok(await self.http.post('/api/body-measurements',json={'date':local_today('America/Sao_Paulo').isoformat(),'weight_kg':80}))
        result=self.ok(await self.http.post('/api/workout-suggestions'))
        self.assertEqual(result['based_on'],{'total_workouts':1,'workout_types':{'weightlifting':1},'has_measurements':True})
        recommendations=self.ok(await self.http.get('/api/body-measurements/recommendations'))
        self.assertEqual(recommendations['workouts_analyzed'],1)
        body={'title':'Treino','content':result['suggestions'],'based_on':result['based_on']}
        saved=self.ok(await self.http.post('/api/workout-suggestions/save',json=body,headers={'Idempotency-Key':'save-insight-001'}))
        self.ok(await self.http.post('/api/workout-suggestions/save',json=body,headers={'Idempotency-Key':'save-insight-001'}))
        self.assertEqual(len(self.ok(await self.http.get('/api/workout-suggestions/saved'))),1)
        self.assertEqual(self.ok(await self.http.get('/api/workout-suggestions/saved',headers={'Authorization':'Bearer bob'})),[])
        url='/api/workout-suggestions/saved/'+saved['insight_id']
        self.assertEqual((await self.http.delete(url,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.ok(await self.http.delete(url))

    async def test_pdf_preview_retains_no_measurement_and_cleans_temporary(self):
        from pathlib import Path
        paths=[]
        async def upload(path,uid):paths.append(path);return SimpleNamespace(uri='test://file')
        with patch('services.study_material_routes._upload',upload),patch('services.study_material_routes._part',return_value={}),\
             patch('services.health_ai_routes.request_gemini',AsyncMock(return_value=SimpleNamespace(text='{"weight_kg":80}'))):
            result=self.ok(await self.http.post('/api/body-measurements/analyze-pdf',files={'file':('body.pdf',b'%PDF fake','application/pdf')}))
        self.assertEqual(result['extracted_data']['weight_kg'],80);self.assertTrue(all(not Path(p).exists() for p in paths))
        self.assertEqual(self.ok(await self.http.get('/api/body-measurements')),[])
