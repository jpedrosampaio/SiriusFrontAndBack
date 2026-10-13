"""Pure decimal calculations. Nutrients are per declared quantity unit, never guessed per 100g."""
from decimal import Decimal, ROUND_HALF_UP,localcontext

MACROS = ('calories', 'protein', 'carbs', 'fat')


def number(value):
    return Decimal(str(value))


def wire(value):
    if value is None:return None
    with localcontext() as context:
        context.prec=max(context.prec,value.adjusted()+4)
        return format(value.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),'f')


def evidence(food):
    return {'source': 'estimated' if food.estimated else 'registered',
        'known_macros': [key for key in MACROS if key in food.model_fields_set and (food.known_macros is None or key in food.known_macros)], 'basis': 'per_unit',
        'portion_label': food.portion_label}


def meal_projection(foods,reported):
    if any(value is not None for value in reported.values()):
        return [{'quantity':1,'nutrition_evidence':None,**{k:reported[k] or 0 for k in MACROS}}]
    return foods or [{'quantity':1,'nutrition_evidence':{'source':'unknown','known_macros':[]},**{k:0 for k in MACROS}}]


def recipe_food(row,quantity=1):
    proof=row.nutrition_evidence
    if proof is None and row.ai_generated:
        proof={'source':'estimated','known_macros':[k for k in MACROS if getattr(row,k+'_per_serving')>0],
            'basis':'per_unit','portion_label':'Uma porção da receita'}
    return {'name':row.name,'quantity':quantity,'unit':'porcao',**{k:getattr(row,k+'_per_serving') for k in MACROS},'nutrition_evidence':proof}


def project(foods,*,rounded=True):
    encode=wire if rounded else lambda value:format(value,'f')
    result = {}
    for key in MACROS:
        buckets = {name: Decimal(0) for name in ('registered', 'estimated', 'legacy_unverified')}
        missing = 0
        for food in foods:
            amount=number(food[key])*number(food['quantity'])
            if not amount.is_finite():
                missing+=1
                continue
            proof = food.get('nutrition_evidence')
            if not isinstance(proof, dict):
                buckets['legacy_unverified'] += amount
                missing += 1
            elif key not in proof.get('known_macros', []) or proof.get('source') not in ('registered', 'estimated'):
                missing += 1
            else:
                buckets[proof['source']] += amount
        total = buckets['registered'] + buckets['estimated']
        result[key] = {**{k: encode(v) for k, v in buckets.items()}, 'known_total': encode(total),
            'total': encode(total) if not missing else None, 'unknown_items': missing, 'unit': 'kcal' if key == 'calories' else 'g'}
    return result
