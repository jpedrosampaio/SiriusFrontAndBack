import hashlib
import json
import logging
from typing import Optional
from fastapi import APIRouter,Request,Cookie,HTTPException,UploadFile,File
from services.nutrition_plans import save_plan,validate_ai_plan
from services.nutrition_plan_dto import GenerationOptions
from pydantic import ValidationError
from services.study_material_routes import read_upload,upload_part
api_router=APIRouter()
get_current_user=get_user_api_key=request_gemini=None


def configure(authenticate,key,gemini):
    global get_current_user,get_user_api_key,request_gemini
    get_current_user,get_user_api_key,request_gemini=authenticate,key,gemini


@api_router.post('/nutrition/meal-plan/generate')
async def generate_meal_plan(request: Request, session_token: Optional[str]=Cookie(None)):
    """Generate a personalized meal plan with AI"""
    auth_header = request.headers.get('Authorization')
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    if not await get_user_api_key(user.user_id):
        raise HTTPException(status_code=503, detail='Serviço de IA indisponível')
    try:
        body = GenerationOptions.model_validate(await request.json()).model_dump()
    except (ValidationError, ValueError):
        raise HTTPException(422, 'Parâmetros do plano alimentar inválidos.')
    objective = body.get('objective', 'saude')
    restrictions = body.get('restrictions', [])
    meals_per_day = body.get('meals_per_day', 5)
    duration = body.get('duration', 'dia')
    calories_target = body.get('calories_target', 0)
    restrictions_text = ''
    if restrictions:
        restrictions_text = f"\nRestrições alimentares: {', '.join(restrictions)}"
    calories_text = ''
    if calories_target > 0:
        calories_text = f'\nMeta calórica: {calories_target} kcal/dia'
    duration_instruction = 'Crie um plano para UM DIA.' if duration == 'dia' else 'Crie um plano para UMA SEMANA (segunda a domingo, 7 dias).'
    prompt = f"""Você é um nutricionista certificado. Gere um plano alimentar completo em JSON.\n\nPARÂMETROS:\n- Objetivo: {objective}\n- Refeições por dia: {meals_per_day}{restrictions_text}{calories_text}\n- {duration_instruction}\n\nFORMATO JSON OBRIGATÓRIO:\n{{\n  "name": "Plano Alimentar - {objective}",\n  "description": "Descrição breve",\n  "calories_total": 2000,\n  "macros": {{"protein_g": 150, "carbs_g": 200, "fat_g": 70, "fiber_g": 30}},\n  "days": [\n    {{\n      "day_name": "dia1",\n      "day_label": "Segunda-feira",\n      "calories": 2000,\n      "meals": [\n        {{\n          "meal_type": "café_da_manhã",\n          "time": "07:00",\n          "name": "Omelete de claras com aveia",\n          "foods": [\n            {{"name": "Clara de ovo", "quantity": "4 unidades", "calories": 68, "protein": 14, "carbs": 0, "fat": 0}},\n            {{"name": "Aveia", "quantity": "40g", "calories": 140, "protein": 5, "carbs": 24, "fat": 3}}\n          ],\n          "total_calories": 208,\n          "preparation": "Bata as claras, adicione sal e temperos. Cozinhe em frigideira antiaderente. Sirva com aveia cozida em água."\n        }}\n      ]\n    }}\n  ],\n  "shopping_list": [\n    {{"name": "Clara de ovo", "quantity": "20 unidades", "category": "proteínas"}},\n    {{"name": "Aveia", "quantity": "200g", "category": "cereais"}}\n  ],\n  "tips": ["Beba no mínimo 2L de água por dia", "Evite comer 2h antes de dormir"]\n}}\n\nIMPORTANTE:\n- Retorne APENAS o JSON, sem markdown, sem ```json\n- Inclua lista de compras (shopping_list) completa\n- Inclua dicas (tips) personalizadas ao objetivo\n- Macros devem ser realistas e adaptados ao objetivo\n- Cada refeição deve ter instrução de preparo\n- {('Retorne apenas 1 dia' if duration == 'dia' else 'Retorne 7 dias')} no array days"""
    try:
        response = await request_gemini(task='nutrition_generation', contents=prompt, config=dict(system_instruction='Você é um nutricionista profissional. Sempre responda em JSON válido.'), user_id=user.user_id)
        response_text = response.text.strip()
        if response_text.startswith('```'):
            response_text = response_text.split('\n', 1)[1] if '\n' in response_text else response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3].strip()
        if response_text.startswith('json'):
            response_text = response_text[4:].strip()
        plan_data = json.loads(response_text)
        validated = validate_ai_plan(plan_data, 'generated', body)
        return await save_plan(user.user_id, validated, 'generated', request.headers.get('Idempotency-Key'), ['generate-meal-plan', body])
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail='Erro ao processar resposta da IA. Tente novamente.')
    except Exception as e:
        logging.error(f'Meal plan generation failed: {e}')
        raise HTTPException(status_code=500, detail=f'Erro ao gerar plano alimentar: {str(e)[:100]}')

@api_router.post('/nutrition/import-plan')
async def import_meal_plan(request: Request, file: UploadFile=File(...), session_token: Optional[str]=Cookie(None), preview: bool=False):
    """Import a meal plan from PDF or image file using AI extraction"""
    auth_header = request.headers.get('Authorization')
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    if not await get_user_api_key(user.user_id):
        raise HTTPException(status_code=503, detail='Serviço de IA indisponível')
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/heic']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail='Formato não suportado. Envie PDF, JPG, PNG ou WEBP.')
    content = await read_upload(file)
    part = await upload_part(content, file.filename, file.content_type, user.user_id)
    try:
        prompt = 'Analise este plano alimentar/dieta e extraia TODAS as refeições em formato JSON estruturado.\n\nPara cada refeição, extraia:\n- meal_type: "breakfast" (café da manhã), "lunch" (almoço), "dinner" (jantar), "snack" (lanche)\n- name: nome da refeição\n- time: horário sugerido (ex: "07:00")\n- foods: lista de alimentos com quantidade\n- calories: calorias estimadas (número)\n- protein: proteína em gramas (número)\n- carbs: carboidratos em gramas (número)\n- fat: gordura em gramas (número)\n- fiber: fibra em gramas (número, opcional)\n- notes: observações adicionais\n\nTambém extraia informações gerais do plano:\n- plan_name: nome do plano\n- goal: objetivo (emagrecimento, hipertrofia, saúde, etc.)\n- daily_calories: meta calórica diária total\n- daily_protein: meta de proteína diária\n- daily_carbs: meta de carboidratos diária\n- daily_fat: meta de gordura diária\n- restrictions: restrições alimentares mencionadas\n- tips: dicas do nutricionista\n\nResponda APENAS com JSON válido neste formato:\n{\n  "plan_name": "Nome do Plano",\n  "goal": "objetivo",\n  "daily_calories": 2000,\n  "daily_protein": 150,\n  "daily_carbs": 200,\n  "daily_fat": 70,\n  "restrictions": ["restrição 1"],\n  "tips": ["dica 1", "dica 2"],\n  "meals": [\n    {\n      "meal_type": "breakfast",\n      "name": "Café da Manhã",\n      "time": "07:00",\n      "foods": [{"name": "Ovos mexidos", "quantity": "3 unidades", "calories": 210}],\n      "calories": 350,\n      "protein": 25,\n      "carbs": 30,\n      "fat": 15,\n      "notes": ""\n    }\n  ]\n}\n\nIMPORTANTE: Retorne APENAS o JSON, sem markdown, sem ```json.'
        response = await request_gemini(task='nutrition_generation', contents=[part, prompt], config=dict(system_instruction='Você é um nutricionista especialista. Extraia com precisão todas as informações do plano alimentar.'), user_id=user.user_id)
        response_text = response.text.strip()
        if response_text.startswith('```'):
            response_text = response_text.split('\n', 1)[1] if '\n' in response_text else response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3].strip()
        if response_text.startswith('json'):
            response_text = response_text[4:].strip()
        plan_data = json.loads(response_text)
        validated = validate_ai_plan(plan_data, 'imported', {}, file.filename)
        if preview:
            from services.nutrition_previews import create_preview
            return await create_preview(user.user_id,validated,hashlib.sha256(content).hexdigest())
        return await save_plan(user.user_id, validated, 'imported', request.headers.get('Idempotency-Key'), ['import-meal-plan', hashlib.sha256(content).hexdigest()])
    except HTTPException:
        raise
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(502, 'A IA retornou um plano alimentar inválido.')

