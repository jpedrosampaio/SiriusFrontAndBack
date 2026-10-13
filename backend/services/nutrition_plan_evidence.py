"""Derived plan summaries, per declared food portion; never inferred per gram."""
from services.nutrition_evidence import MACROS,project,meal_projection,number


def reviewed_plan(body):
    result=body.model_copy(deep=True)
    all_foods=[]
    for day in result.days:
        day_foods=[]
        for meal in day.meals:
            foods=[{'quantity':1,**{k:getattr(food,k) for k in MACROS},
                'nutrition_evidence':{'source':'estimated','known_macros':food.known_macros or []}} for food in meal.foods]
            foods=meal_projection(foods,{k:None for k in MACROS})
            totals=project(foods,rounded=False)
            for key in MACROS:setattr(meal,key,float(totals[key]['total']) if totals[key]['total'] is not None else None)
            day_foods.extend(foods)
        calories=project(day_foods,rounded=False)['calories']['total']
        day.calories=float(calories) if calories is not None else None
        all_foods.extend(day_foods)
    totals=project(all_foods,rounded=False)
    for key in MACROS:
        value=totals[key]['total']
        setattr(result,'daily_'+key,float(number(value)/len(result.days)) if result.days and value is not None else None)
    return result
