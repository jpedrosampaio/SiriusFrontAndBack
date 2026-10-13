import json
import logging
from typing import Optional
from fastapi import APIRouter,Request,Cookie,HTTPException
from services.recipe_routes import nutrition_goals,save_recipe
api_router=APIRouter()
get_current_user=get_user_api_key=request_gemini=None


def configure(authenticate,key,gemini):
    global get_current_user,get_user_api_key,request_gemini
    get_current_user,get_user_api_key,request_gemini=authenticate,key,gemini


@api_router.post('/nutrition/recipes/suggest')
async def suggest_recipe(request: Request, preferences: dict, session_token: Optional[str]=Cookie(None)):
    """Get AI-suggested recipe based on preferences"""
    auth_header = request.headers.get('Authorization')
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    goals = await nutrition_goals(user.user_id)
    goal_info = ''
    if goals.get('confirmed_fields'):
        goal_info = '\nMetas explicitamente confirmadas (não inferir necessidades):\n' + '\n'.join(
            f'- {key}: {goals[key]}' for key in goals['confirmed_fields'] if key.startswith('daily_'))
    diet_type = preferences.get('diet_type', '')
    meal_type = preferences.get('meal_type', '')
    ingredients = preferences.get('available_ingredients', [])
    restrictions = preferences.get('restrictions', [])
    cuisine = preferences.get('cuisine', '')
    max_time = preferences.get('max_prep_time_minutes', 60)
    prompt = f"""Sugira uma receita saudável com as seguintes preferências:\n{goal_info}\n- Tipo de refeição: {meal_type or 'qualquer'}\n- Tipo de dieta: {diet_type or 'balanceada'}\n- Ingredientes disponíveis: {(', '.join(ingredients) if ingredients else 'qualquer')}\n- Restrições alimentares: {(', '.join(restrictions) if restrictions else 'nenhuma')}\n- Culinária preferida: {cuisine or 'qualquer'}\n- Tempo máximo de preparo: {max_time} minutos\n\nForneça a resposta em formato JSON com a seguinte estrutura:\n{{\n    "name": "Nome da Receita",\n    "description": "Breve descrição",\n    "ingredients": [{{"name": "ingrediente", "quantity": "quantidade", "unit": "unidade"}}],\n    "instructions": ["Passo 1", "Passo 2"],\n    "prep_time_minutes": 15,\n    "cook_time_minutes": 30,\n    "servings": 4,\n    "calories_per_serving": 350,\n    "protein_per_serving": 25,\n    "carbs_per_serving": 40,\n    "fat_per_serving": 12,\n    "tags": ["saudável", "rápido"],\n    "tips": "Dica extra"\n}}"""
    if not await get_user_api_key(user.user_id):
        raise HTTPException(status_code=503, detail='Serviço de IA não disponível')
    try:
        response = await request_gemini(task='nutrition_generation', contents=prompt, config=dict(system_instruction='Você é um nutricionista e chef experiente. Forneça receitas saudáveis e práticas. Sempre responda em JSON válido.', response_mime_type='application/json', response_schema={'type': 'OBJECT', 'required': ['name', 'description', 'ingredients', 'instructions'], 'properties': {'name': {'type': 'STRING'}, 'description': {'type': 'STRING'}, 'ingredients': {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {'name': {'type': 'STRING'}, 'quantity': {'type': 'STRING'}, 'unit': {'type': 'STRING'}}}}, 'instructions': {'type': 'ARRAY', 'items': {'type': 'STRING'}}, 'prep_time_minutes': {'type': 'INTEGER'}, 'cook_time_minutes': {'type': 'INTEGER'}, 'servings': {'type': 'INTEGER'}, 'calories_per_serving': {'type': 'INTEGER'}, 'protein_per_serving': {'type': 'INTEGER'}, 'carbs_per_serving': {'type': 'INTEGER'}, 'fat_per_serving': {'type': 'INTEGER'}, 'tags': {'type': 'ARRAY', 'items': {'type': 'STRING'}}, 'tips': {'type': 'STRING'}}}), user_id=user.user_id)
        response_text = response.text.strip()
        try:
            recipe_data = json.loads(response_text)
        except json.JSONDecodeError:
            cleaned = response_text
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            import re
            cleaned = re.sub(',\\s*}', '}', cleaned)
            cleaned = re.sub(',\\s*]', ']', cleaned)
            recipe_data = json.loads(cleaned)
        return await save_recipe(user.user_id, recipe_data, request.headers.get('Idempotency-Key'), preferences)
    except HTTPException:
        raise
    except json.JSONDecodeError as je:
        logging.error(f'Recipe JSON parse error: {je}')
        raise HTTPException(status_code=500, detail='Erro ao interpretar resposta da IA. Tente novamente.')
    except Exception as e:
        logging.error(f'Recipe suggestion failed: {e}')
        raise HTTPException(status_code=500, detail=f'Falha ao gerar receita: {str(e)}')
