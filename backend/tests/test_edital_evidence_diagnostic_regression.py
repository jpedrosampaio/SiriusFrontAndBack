"""Documentary rejection diagnostics, never real provider IO or private content."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.validation_diagnostics import documentary_failure, safe_validation
from services.edital_semantics import EvidenceError, validate_citation
from edital_pipeline_contracts import Citation
from services.edital_pipeline_worker import IncrementalHandler

class DocumentaryDiagnostics(unittest.IsolatedAsyncioTestCase):
    def test_exact_citation_gate_remains_strict_and_diagnostic_is_finite(self):
        source={'p0001-b0001':{'page':1,'text':'Documento sintético'}}
        with self.assertRaises(EvidenceError) as failed:
            validate_citation(Citation(page=1,block_id='p0001-b0001',quote='PRIVATE-UNSUPPORTED-QUOTE'),source)
        self.assertEqual(documentary_failure(failed.exception),{'stage':'documentary','code':'source_excerpt_mismatch','path':'$'})
        self.assertEqual(documentary_failure(EvidenceError('PRIVATE-KEY'))['code'],'documentary_rejected')
        self.assertIsNone(safe_validation({'stage':'documentary','code':'PRIVATE-KEY'}))

    async def test_worker_preserves_finite_rule_without_retrying_provider(self):
        router=SimpleNamespace(generate=AsyncMock())
        credentials=SimpleNamespace(get=AsyncMock())
        handler=IncrementalHandler(router,credentials,None)
        with patch('services.edital_pipeline_worker.units.snapshot',AsyncMock(side_effect=EvidenceError('source_reference_mismatch'))), patch('services.edital_pipeline_worker.units.fail',AsyncMock()) as fail:
            await handler.execute(SimpleNamespace())
        fail.assert_awaited_once()
        self.assertEqual(fail.await_args.kwargs['validation'],{'stage':'documentary','code':'source_reference_mismatch','path':'$'})
        router.generate.assert_not_awaited(); credentials.get.assert_not_awaited()
