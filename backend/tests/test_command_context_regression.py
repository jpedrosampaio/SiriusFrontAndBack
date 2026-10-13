import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.context_limits import bounded_context
from ai.agent import SiriusAgent, AgentPlan
from ai.actions import Preferences
from ai.memory import MemoryInput
from ai.types import AIResult


class CommandContext(unittest.IsolatedAsyncioTestCase):
    async def test_blocked_study_tool_never_eagerly_reads_or_reaches_provider(self):
        core=SimpleNamespace(page_context=AsyncMock(return_value={}),read=AsyncMock(return_value=[{'name':'Private syllabus'}]))
        credentials=SimpleNamespace(get=AsyncMock(return_value={'groq':'mock-only'}))
        memory=SimpleNamespace(list=AsyncMock(return_value=[]))
        actions=SimpleNamespace(preferences=AsyncMock(return_value=Preferences(blocked_tools=['get_study_progress'])))
        router=SimpleNamespace(settings=SimpleNamespace(rag=True),generate=AsyncMock(return_value=AIResult(data=AgentPlan(reply='Mock response',calls=[]),provider='mock',model='fake')))
        retrieval=SimpleNamespace(ensure_selection=AsyncMock(),search=AsyncMock(return_value={'method':'lexical','citations':[{'text':'Private indexed syllabus'}]}))
        agent=SiriusAgent(core,router,credentials,actions,memory,retrieval)
        body=SimpleNamespace(page='/studies',message='Quero estudar neste caderno',page_context='{}',conversation_id='test',request_id='test')
        response=await agent.respond('owned',body,json.dumps({'history':[]}))
        core.read.assert_not_awaited()
        retrieval.ensure_selection.assert_not_awaited();retrieval.search.assert_not_awaited()
        self.assertEqual(response['retrieval_method'],'blocked');self.assertEqual(response['citations'],[])
        prompt=json.loads(router.generate.await_args.kwargs['prompt'])
        self.assertNotIn('owned_notebooks',prompt['context'])
        self.assertNotIn('Private syllabus',str(prompt))
        self.assertNotIn('Private indexed syllabus',str(prompt))
        self.assertNotIn('get_study_progress',router.generate.await_args.kwargs['system'])

    async def test_enabled_rag_preserves_explicit_owned_study_selection_when_allowed(self):
        selected={'notebook':{'notebook_id':'owned-notebook'}}
        core=SimpleNamespace(page_context=AsyncMock(return_value=selected),read=AsyncMock(return_value=[]))
        credentials=SimpleNamespace(get=AsyncMock(return_value={'groq':'mock-only'}))
        memory=SimpleNamespace(list=AsyncMock(return_value=[]))
        actions=SimpleNamespace(preferences=AsyncMock(return_value=Preferences()))
        router=SimpleNamespace(settings=SimpleNamespace(rag=True),generate=AsyncMock(return_value=AIResult(data=AgentPlan(reply='Mock response',calls=[]),provider='mock',model='fake')))
        evidence={'method':'lexical','citations':[{'text':'Owned selected source'}]}
        retrieval=SimpleNamespace(ensure_selection=AsyncMock(),search=AsyncMock(return_value=evidence))
        agent=SiriusAgent(core,router,credentials,actions,memory,retrieval)
        body=SimpleNamespace(page='/studies',message='Explique a fonte.',page_context='{}',conversation_id='test',request_id='test')
        response=await agent.respond('owned',body,json.dumps({'history':[]}))
        retrieval.ensure_selection.assert_awaited_once_with('owned',selected)
        retrieval.search.assert_awaited_once_with('owned',body.message,'owned-notebook')
        self.assertEqual(response['citations'],evidence['citations'])
        self.assertIn('Owned selected source',router.generate.await_args.kwargs['prompt'])

    def test_limits_preserve_complete_facts_and_disclose_omissions(self):
        raw={'date':'2026-10-13','selection':{'exercise':{'title':'Supino'}},'large_history':['x'*500]*1000,'finance':{'amount':'0.30','bank_balance':None}}
        result=bounded_context(raw,3000)
        self.assertLessEqual(len(json.dumps(result,ensure_ascii=False)),3000)
        self.assertEqual(result['finance'],raw['finance']);self.assertEqual(result['selection'],raw['selection'])
        self.assertIn('large_history',result['context_limits']['omitted_sections']);self.assertEqual(len(raw['large_history']),1000)

    def test_memory_types_cannot_claim_verified_origins_or_inferences(self):
        for category in ('fact','preference','decision'):
            self.assertEqual(MemoryInput(category=category,content='Declared').category,category)
        with self.assertRaises(ValueError):MemoryInput(category='fact',content='Guess',provenance={'verified':True})

    async def test_agent_minimizes_scope_and_strips_blocked_client_hints_before_read(self):
        core=SimpleNamespace(page_context=AsyncMock(return_value={}),read=AsyncMock(return_value={}),life_context=AsyncMock(return_value={}))
        credentials=SimpleNamespace(get=AsyncMock(return_value={'groq':'mock-only'}))
        memory=SimpleNamespace(list=AsyncMock(return_value=[{'category':'fact','content':'Scoped private diet','scope':'nutrition'},
            {'category':'preference','content':'Global declared','scope':'global','provenance':{'origin':'user_declared','verified':False}}]))
        actions=SimpleNamespace(preferences=AsyncMock(return_value=Preferences(blocked_tools=['get_finance_state','get_wrong_questions','get_calendar'])))
        router=SimpleNamespace(settings=SimpleNamespace(rag=False),generate=AsyncMock(return_value=AIResult(data=AgentPlan(reply='Mock response',calls=[]),provider='mock',model='fake')))
        agent=SiriusAgent(core,router,credentials,actions,memory,None)
        body=SimpleNamespace(page='/finance',message='Explique a seleção.',page_context=json.dumps({'transaction_id':'foreign-hint',
            'question_id':'question-hint','event_id':'event-hint','query':'?transaction=foreign-hint&question=question-hint&event=event-hint',
            'facts':{'balance':9999}}),conversation_id='test',request_id='test')
        await agent.respond('owned',body,json.dumps({'history':[],'summary_extracts':''}))
        hint=json.loads(core.page_context.await_args.args[1]);self.assertNotIn('transaction_id',hint);self.assertNotIn('transaction=',hint['query'])
        self.assertNotIn('question_id',hint);self.assertNotIn('event_id',hint);self.assertEqual(hint['query'],'')
        prompt=json.loads(router.generate.await_args.kwargs['prompt']);self.assertNotIn('Scoped private diet',str(prompt))
        self.assertIn('Global declared',str(prompt));self.assertEqual(prompt['context']['memories'][0]['verified'],False)
        core.read.assert_not_awaited()
