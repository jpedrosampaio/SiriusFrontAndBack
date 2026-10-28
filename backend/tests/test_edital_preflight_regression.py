"""Legacy checkpoint sizing before provider IO; no production or real AI."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.edital_pipeline_budget import estimate
from services.edital_pipeline_worker import IncrementalHandler

class LegacyPreflight(unittest.IsolatedAsyncioTestCase):
    def test_forecast_includes_real_binary_splits_and_each_future_verification(self):
        generation=uuid4();state=SimpleNamespace(inventory=SimpleNamespace(generation=generation),selected_role_id=None,scopes={},
            budget=SimpleNamespace(reserved_attempts=23,provider_limit=120),provider_approval=None,phase='inventory')
        for count,parts in ((60,1),(61,2),(120,2),(121,3),(239,4),(240,4)):
            with self.subTest(count=count):
                plan=estimate(state,[{'generation':generation,'kind':'inventory','status':'pending','unit_key':'a','source_count':count}])
                self.assertEqual(plan['stages']['inventory'],parts);self.assertEqual(plan['stages']['verify'],parts)
                self.assertEqual(plan['minimum_total_attempts'],23+2*parts)
                self.assertEqual(plan['includes_preflight_splits'],parts>1)
        plan=estimate(state,[{'generation':generation,'kind':'inventory','status':'completed','unit_key':'a','source_count':120}])
        self.assertEqual(plan['stages']['inventory'],0);self.assertEqual(plan['stages']['verify'],1)
        self.assertFalse(plan['includes_preflight_splits']);self.assertEqual(state.budget.provider_limit,120)

    async def test_legacy_oversize_uses_existing_split_signal_before_model_or_credentials(self):
        router=SimpleNamespace(generate=AsyncMock());credentials=SimpleNamespace(get=AsyncMock())
        snapshot={'manifest':SimpleNamespace(provider_approval=SimpleNamespace(diagnostic_case=None)),
            'primary':[{'id':f'p0001-b{index:04d}','page':1,'text':'Synthetic'} for index in range(1,62)]}
        with patch('services.edital_pipeline_worker.units.snapshot',AsyncMock(return_value=snapshot)),patch('services.edital_pipeline_worker.units.fail',AsyncMock()) as fail,patch('services.edital_pipeline_worker.partition_contract') as factory:
            await IncrementalHandler(router,credentials,None).execute(SimpleNamespace(kind='inventory'))
        self.assertEqual(fail.await_args.args[1],'input_limit');self.assertFalse(fail.await_args.kwargs['error'].attempted)
        factory.assert_not_called();credentials.get.assert_not_awaited();router.generate.assert_not_awaited()
