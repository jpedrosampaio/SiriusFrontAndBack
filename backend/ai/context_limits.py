"""Deterministic prompt minimization; facts are never rescaled or inferred."""
import json


def bounded_context(value, limit=18000):
    """Keep complete top-level sections that fit, disclose omissions explicitly.

    Server/API histories remain intact. Never cut JSON or turn partial histories into totals.
    Selection and current-page facts are ordered by the caller before optional sections.
    """
    result={};omitted=[]
    for key,section in value.items():
        candidate={**result,key:section}
        if len(json.dumps(candidate,ensure_ascii=False,default=str))<=limit-1000:
            result[key]=section
        else:omitted.append(key)
    if omitted:result['context_limits']={'omitted_sections':omitted,
        'limitation':'Seções excederam o limite de contexto. Não inferir seus dados; consultar fontes específicas ou solicitar escopo menor.'}
    return result
