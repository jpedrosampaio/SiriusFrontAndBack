import json
import logging
from typing import Optional
from fastapi import APIRouter,Request,Cookie,UploadFile,File,HTTPException
from services import body_measurements as sql_body
from services.study_material_routes import upload_part,read_upload
api_router=APIRouter()
get_current_user=call_llm=request_gemini=None

def configure(authenticate,llm,gemini):
    global get_current_user,call_llm,request_gemini
    get_current_user,call_llm,request_gemini=authenticate,llm,gemini

@api_router.post("/workout-suggestions")
async def get_ai_workout_suggestions(request: Request, session_token: Optional[str] = Cookie(None)):
    """Get AI-powered workout suggestions based on user's history and goals"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    workout_summary,total_workouts,latest_measurement=await sql_body.suggestion_context(user.user_id)

    prompt = f"""Com base no histórico de treinos e dados do usuário, sugira um plano de treino personalizado.

HISTÓRICO DE TREINOS (últimos 30 dias):
- Total de treinos: {total_workouts}
- Por tipo: {json.dumps(workout_summary, indent=2)}

"""

    if latest_measurement:
        prompt += f"""MEDIDAS CORPORAIS:
- Peso: {latest_measurement.get('weight_kg', 'N/A')} kg
- Altura: {latest_measurement.get('height_cm', 'N/A')} cm
- Gordura corporal: {latest_measurement.get('body_fat_percentage', 'N/A')}%
- Massa muscular: {latest_measurement.get('muscle_mass_kg', 'N/A')} kg

"""

    prompt += """Por favor, forneça:
1. Análise do perfil de treino atual
2. Sugestão de treino para a próxima semana (com exercícios específicos)
3. Dicas de intensidade e progressão
4. Recomendações de descanso e recuperação
5. Sugestões de nutrição pré e pós-treino

Responda em português de forma prática e motivadora."""

    try:
        response = await call_llm(
            prompt=prompt,
            session_id=f"workout_suggestions_{user.user_id}",
            system_message="Você é um personal trainer experiente e nutricionista esportivo. Forneça sugestões personalizadas e práticas.",
            user_id=user.user_id
        , task='workout_generation')

        return {
            "suggestions": response,
            "based_on": {
                "total_workouts": total_workouts,
                "workout_types": workout_summary,
                "has_measurements": latest_measurement is not None
            }
        }

    except Exception as e:
        logging.error(f"Workout suggestions failed: {e}")
        raise HTTPException(status_code=500, detail="Não foi possível gerar sugestões. Tente novamente.")


@api_router.post("/body-measurements/analyze-pdf")
async def analyze_pdf_measurement(
    request: Request,
    file: UploadFile = File(...),
    session_token: Optional[str] = Cookie(None)
):
    """Analyze a PDF file containing body measurement data using AI"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Read file content
    content = await read_upload(file)

    # Use Gemini to analyze the PDF
    try:
        system_message = """Você é um especialista em análise de avaliações físicas e bioimpedância.
            Analise o documento e extraia TODOS os dados disponíveis.
            Responda APENAS em formato JSON válido com os campos encontrados.
            Use os seguintes nomes de campos (deixe null se não encontrado):
            - weight_kg, height_cm, body_fat_percentage, muscle_mass_kg
            - bone_mass_kg, water_percentage, visceral_fat, metabolic_age, bmr_kcal
            - neck_cm, shoulders_cm, chest_cm, waist_cm, abdomen_cm, hips_cm
            - left_arm_cm, right_arm_cm, left_forearm_cm, right_forearm_cm
            - left_thigh_cm, right_thigh_cm, left_calf_cm, right_calf_cm
            - date (formato YYYY-MM-DD), notes (observações relevantes)
            - recommendations (array de recomendações baseadas nos dados)"""

        part=await upload_part(content,file.filename,'application/pdf',user.user_id)

        response = await request_gemini(task='assistant_chat', contents=[part, 'Analise este documento de avaliação física/bioimpedância e extraia todos os dados em JSON:'], config=dict(system_instruction=system_message), user_id=user.user_id)

        # Clean up temp file

        # Try to parse JSON from response
        try:
            # Remove markdown code blocks if present
            json_str = response.text.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]

            extracted_data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            # If JSON parsing fails, return raw analysis
            extracted_data = {"raw_analysis": response.text, "parse_error": True}

        return {
            "success": True,
            "extracted_data": extracted_data,
            "filename": file.filename
        }

    except Exception as e:
        logging.error(f"PDF analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze PDF: {str(e)}")


@api_router.get("/body-measurements/recommendations")
async def get_workout_recommendations(request: Request, session_token: Optional[str] = Cookie(None)):
    """Get AI-powered workout and health recommendations based on body measurements"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    measurements,workouts=await sql_body.recommendation_context(user.user_id)

    if not measurements:
        return {
            "recommendations": ["Registre suas medidas corporais para receber recomendações personalizadas."],
            "based_on": "no_data"
        }

    latest = measurements[0]

    prompt = f"""Com base nos seguintes dados corporais do usuário, forneça recomendações personalizadas de treino e saúde:

MEDIDAS ATUAIS:
- Peso: {latest.get('weight_kg', 'N/A')} kg
- Altura: {latest.get('height_cm', 'N/A')} cm
- IMC: {latest.get('bmi', 'N/A')}
- Gordura corporal: {latest.get('body_fat_percentage', 'N/A')}%
- Massa muscular: {latest.get('muscle_mass_kg', 'N/A')} kg
- Cintura: {latest.get('waist_cm', 'N/A')} cm
- Gordura visceral: {latest.get('visceral_fat', 'N/A')}

HISTÓRICO DE TREINOS (últimos 10):
{json.dumps([{"name": w.get("name"), "type": w.get("activity_type"), "duration": w.get("duration_minutes")} for w in workouts], indent=2)}

Forneça:
1. 3-5 recomendações específicas de treino
2. Dicas de nutrição
3. Áreas de foco prioritárias
4. Metas sugeridas para os próximos 30 dias

Responda em português de forma direta e motivadora."""

    try:
        response = await call_llm(
            prompt=prompt,
            session_id=f"recommendations_{user.user_id}",
            system_message="Você é um personal trainer e nutricionista experiente. Forneça recomendações práticas e motivadoras.",
            user_id=user.user_id
        , task='workout_generation')
        return {
            "recommendations": response,
            "based_on": latest,
            "workouts_analyzed": len(workouts)
        }
    except Exception as e:
        logging.error(f"Recommendations generation failed: {e}")
        return {
            "recommendations": "Não foi possível gerar recomendações no momento. Tente novamente mais tarde.",
            "error": str(e)
        }
