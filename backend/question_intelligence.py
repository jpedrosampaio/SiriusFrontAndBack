"""Provider-neutral question contracts and deterministic evidence projections."""
import hashlib
import re
import unicodedata
from collections import defaultdict, Counter
from dataclasses import dataclass

VERSION='questions-1'
ERROR_ALIASES={'unknown':'knowledge_gap','forgot':'memory','concepts':'concept_confusion'}
PROVENANCE={'manual':'user_created','user_created':'user_created','error_review':'user_created','imported':'imported','pdf_import':'imported',
    'ai_generated':'ai_generated','generated':'ai_generated','official':'official'}


@dataclass(frozen=True)
class QuestionProvider:
    name: str
    provenance: str
    available: bool=True

    def origin(self, metadata=None):
        if not self.available:raise ValueError('Provider unavailable')
        return question_origin(self.provenance,metadata)


PROVIDERS={name:QuestionProvider(name,origin,available) for name,origin,available in (
    ('manual','user_created',True),('import','imported',True),('official','official',True),
    ('generated','ai_generated',True),('future_external_provider','unknown',False))}


def provider_for_source(source):
    name={'manual':'manual','error_review':'manual','imported':'import','pdf_import':'import',
        'official':'official','ai_generated':'generated','generated':'generated'}.get(source)
    return PROVIDERS.get(name)


def question_origin(source,metadata=None):
    metadata=metadata or {}
    # AI cannot be promoted to official by arbitrary nested metadata.
    if source in ('ai_generated','generated') or metadata.get('generated_by_ai') is True:return 'ai_generated'
    if source=='official':return 'official' if metadata.get('official_evidence_verified') is True else 'unknown'
    return PROVENANCE.get(source,'unknown')


def normalize(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(text).lower())
        if not unicodedata.combining(c)).split())


def error_bank(rows):
    groups=defaultdict(list)
    for row in rows:
        key=(row['notebook_id'],row.get('topic_key'),row.get('internal_question_id') or normalize(row.get('question','')))
        groups[key].append(row)
    result=[]
    for key,evidence in groups.items():
        ordered=sorted(evidence,key=lambda r:(r.get('answered_at') or r['date'],r['attempt_id']))
        errors=[r for r in ordered if not r['correct'] and not r.get('skipped')]
        if not errors:continue
        later=[r for r in ordered if r['correct'] and (r.get('answered_at') or r['date'])>(errors[-1].get('answered_at') or errors[-1]['date'])]
        last=errors[-1]
        result.append({'question_id':last.get('internal_question_id'),'notebook_id':key[0],'topic_key':key[1],
            'title':last['title'],'errors':len(errors),'last_error_at':last.get('answered_at') or last['date'],
            'error_cause':ERROR_ALIASES.get(last.get('error_reason'),last.get('error_reason') or 'unclassified'),
            'recovered':bool(later),'later_evidence_ids':[r['attempt_id'] for r in later][-20:],
            'error_evidence_ids':[r['attempt_id'] for r in errors][-20:]})
    result.sort(key=lambda r:(-r['errors'],r['last_error_at'],r['question_id'] or ''))
    return {'items':result[:100],'question_count':len(result),'recovered_questions':sum(r['recovered'] for r in result),
        'recovery_rate':round(100*sum(r['recovered'] for r in result)/len(result),1) if result else None,
        'basis':'later_answer_to_same_scoped_question','partial':len(result)>100}


def forensic_clusters(rows):
    groups=defaultdict(list)
    for row in rows:
        if row['correct'] or row.get('skipped'):continue
        reason=ERROR_ALIASES.get(row.get('error_reason'),row.get('error_reason') or 'unclassified')
        groups[(row['notebook_id'],row.get('topic_key'),reason)].append(row)
    clusters=[]
    for (notebook,key,reason),evidence in groups.items():
        distinct={normalize(r.get('question','')) or r.get('internal_question_id') for r in evidence}
        if len(distinct)<3:continue
        words=Counter()
        for row in evidence:
            words.update(set(re.findall(r'\b[a-z]{5,}\b',normalize(row.get('question',''))[:12000])))
        terms=sorted((w for w,count in words.items() if count>=3),key=lambda w:(-words[w],w))[:8]
        fingerprint=hashlib.sha256(f'{notebook}:{key}:{reason}:{VERSION}'.encode()).hexdigest()
        clusters.append({'fingerprint':fingerprint,'notebook_id':notebook,'topic_key':key,'reason':reason,
            'question_count':len(distinct),'attempt_ids':[r['attempt_id'] for r in evidence[:100]],
            'question_ids':sorted({r['internal_question_id'] for r in evidence if r.get('internal_question_id')})[:100],
            'terms':terms,'classification':'suggestion','confidence':'heuristic_same_topic_and_cause',
            'notice':'Recorrência no mesmo assunto e motivo informado; conceito comum exige confirmação.','rule_version':VERSION})
    return sorted(clusters,key=lambda c:(-c['question_count'],c['fingerprint']))[:50]


def validate_generated_question(question):
    """Structural validation is not a claim of factual correctness."""
    options=question.get('options');answer=str(question.get('correct_answer') or '').strip()
    if not isinstance(question.get('question_text'),str) or not 1<=len(question['question_text'])<=12000:
        return False
    if not isinstance(question.get('explanation'),str) or not 1<=len(question['explanation'])<=8000:
        return False
    if not isinstance(options,list) or not 2<=len(options)<=5 or any(not isinstance(o,str) or not 1<=len(o)<=4000 for o in options):
        return False
    normalized=[normalize(re.sub(r'^[A-E][).:]\s*','',str(option))) for option in options]
    if any(not item for item in normalized) or len(set(normalized))!=len(normalized):return False
    valid_letters=list('ABCDE'[:len(options)])
    if answer not in valid_letters and normalize(answer) not in normalized:return False
    return question.get('validation_confidence') not in ('low','baixa')
