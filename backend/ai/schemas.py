"""Provider transport projection. Canonical JSON Schema/Pydantic remain gates.

Gemini generateContent supports a subset; notably $ref nodes may not have
non-$ siblings. Strip annotations/locally enforced scalar constraints and
convert const to enum, retaining references and structural requirements.
No document, response or credential enters this module.
"""
from copy import deepcopy
import json
from ai.types import AIError

TRANSPORT_VERSION = 'structured-transport/3'
PROFILES = {'gemini_json_v2', 'groq_json_v2'}
IGNORED = {'title','description','default','examples','minLength','maxLength','pattern',
    'minProperties','maxProperties','$schema','$id'}
SUPPORTED = {'$defs','$ref','type','format','enum','items','prefixItems','minItems','maxItems',
    'minimum','maximum','anyOf','oneOf','properties','additionalProperties','required'}


def incompatible(reason):
    return AIError('invalid_request', incompatibility=reason)


def transport_schema(schema, profile):
    if profile not in PROFILES:raise incompatible('model_capability')
    definitions=schema.get('$defs',{})
    nodes=0
    def project(value,depth=0):
        nonlocal nodes
        nodes+=1
        if nodes>4096 or depth>32:raise incompatible('schema_complexity')
        if isinstance(value,bool):return value
        if not isinstance(value,dict):raise incompatible('schema_feature')
        result={}
        if '$ref' in value:
            reference=value['$ref']
            if not isinstance(reference,str) or not reference.startswith('#/$defs/') or reference[8:] not in definitions:
                raise incompatible('schema_reference')
            # Locally validate every sibling on the original contract. Gemini
            # forbids default/title/constraints beside a $ref, even if nullable.
            return {'$ref':reference}
        for key,item in value.items():
            if key in IGNORED:continue
            if key=='const':
                if isinstance(item,(str,int,float)) and not isinstance(item,bool):result['enum']=[item]
                continue
            if key not in SUPPORTED:raise incompatible('schema_feature')
            if key in ('properties','$defs'):
                result[key]={name:project(child,depth+1) for name,child in item.items()}
            elif key in ('items','additionalProperties'):
                result[key]=project(item,depth+1)
            elif key in ('anyOf','oneOf','prefixItems'):
                result[key]=[project(child,depth+1) for child in item]
            else:result[key]=deepcopy(item)
        return result
    result=project(schema)
    if definitions and '$defs' not in result:result['$defs']={name:project(value) for name,value in definitions.items()}
    # Reject recursive transport graphs instead of consuming quota on a model-
    # dependent unrolling rule. Acyclic shared definitions remain compact.
    visited=set()
    def references(value,stack=()):
        if len(stack)>32:raise incompatible('schema_complexity')
        if isinstance(value,dict):
            if '$ref' in value:
                name=value['$ref'][8:]
                if name in stack:raise incompatible('schema_reference')
                if name not in visited:
                    references(result['$defs'][name],(*stack,name));visited.add(name)
            else:
                for key,child in value.items():
                    if key!='$defs':references(child,stack)
        elif isinstance(value,list):
            for child in value:references(child,stack)
    references(result)
    if len(json.dumps(result,separators=(',',':')).encode())>60000:raise incompatible('schema_complexity')
    return result
