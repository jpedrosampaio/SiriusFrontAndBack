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


def project(foods):
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
        result[key] = {**{k: wire(v) for k, v in buckets.items()}, 'known_total': wire(total),
            'total': wire(total) if not missing else None, 'unknown_items': missing, 'unit': 'kcal' if key == 'calories' else 'g'}
    return result
