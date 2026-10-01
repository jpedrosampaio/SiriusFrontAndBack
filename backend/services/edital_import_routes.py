"""Existing AI import prompts, with PostgreSQL validation and atomic writes."""
import asyncio
import hashlib
import json
import uuid
from typing import Optional
from fastapi import APIRouter,Cookie,File,Form,HTTPException,Request,UploadFile
from edital_quality import edital_context,needs_disciplines,mark_discipline_quality
from services import edital_analyses as sql_edital
from services import edital_programs as programs

router=APIRouter()


def configure(authenticate,llm,gemini,key,hydrate,extract):
    global get_current_user,call_llm,call_gemini,get_user_api_key,_hydrate_disciplinas_from_text,extract_pdf_text
    get_current_user,call_llm,call_gemini,get_user_api_key,_hydrate_disciplinas_from_text,extract_pdf_text=authenticate,llm,gemini,key,hydrate,extract

@router.post("/study/programs/import-edital")
async def import_edital(
    request: Request,
    file: UploadFile = File(...),
    area_id: str = Form(...),
    target_date: Optional[str] = Form(None),
    hours_per_day: float = Form(4.0),
    days_per_week: int = Form(5),
    session_token: Optional[str] = Cookie(None)
):
    """Upload a PDF of an edital (public exam notice) and generate a complete study program with AI"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    await programs.validate_area(user.user_id,area_id,hours_per_day,days_per_week,target_date)

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos")

    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Limite de 20MB.")

    try:
        user_api_key = await get_user_api_key(user.user_id)
        if not user_api_key:
            raise HTTPException(status_code=400, detail="Configure sua chave Gemini no perfil para usar este recurso.")

        pdf_text = (await asyncio.to_thread(extract_pdf_text, content)) or ""
        if not pdf_text.strip():
            raise HTTPException(status_code=400, detail="Não foi possível extrair texto do PDF.")
        text_clip = edital_context(pdf_text).replace("{", "{{").replace("}", "}}")

        prompt_text = f"""Analise o edital de concurso abaixo e retorne APENAS JSON válido.

Gere um programa de estudos completo com base neste edital.
O aluno tem {hours_per_day} horas disponíveis por dia, {days_per_week} dias por semana para estudar.
{"A data da prova é: " + target_date + "." if target_date else "Não há data definida para a prova."}

Responda APENAS com JSON no formato (sem texto adicional):
{{"concurso":{{"nome":"","orgao":"","banca":"","cargo":"","vagas":"","remuneracao":"","escolaridade":"","data_prova":""}},"disciplinas":[{{"nome":"","peso":3,"num_questoes":10,"topicos":[],"conteudo_programatico":[{{"assunto":"","subtopicos":[]}}],"dificuldade":"media","dicas_estudo":"","recursos_recomendados":""}}],"cronograma_semanal":[{{"dia":"Segunda","blocos":[{{"disciplina":"","duracao_minutos":120,"tipo_estudo":"Teoria","prioridade":"alta","assuntos_foco":[]}}]}}],"estrategia":{{"resumo":"","fase_1":"","fase_2":"","fase_3":"","dicas_gerais":[],"materias_prioritarias":[],"horas_semanais_total":0}}}}

TEXTO DO EDITAL:
{text_clip}"""

        system_msg = "Você é um especialista em concursos públicos brasileiros e planejamento de estudos."

        result, error_type = await call_gemini(prompt_text, system_msg, user_api_key, timeout_override=180, user_id=user.user_id)
        if not result:
            if error_type == "quota":
                raise HTTPException(status_code=500, detail="Sua cota da API Gemini esgotou.")
            if error_type == "invalid":
                raise HTTPException(status_code=500, detail="Sua chave Gemini é inválida.")
            raise HTTPException(status_code=500, detail=f"Erro ao contactar API Gemini (tipo={error_type}).")

        json_str = result.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        parsed = json.loads(json_str.strip())

        concurso_info = parsed.get("concurso", {})
        disciplinas = parsed.get("disciplinas", [])
        cronograma = parsed.get("cronograma_semanal", [])
        estrategia = parsed.get("estrategia", {})

        if not disciplinas:
            raise HTTPException(status_code=400, detail="Não foi possível extrair disciplinas do edital. Verifique se o PDF contém o conteúdo programático.")

        return await programs.create(user.user_id,request.headers.get('Idempotency-Key'),
            ['import-edital',hashlib.sha256(content).hexdigest(),area_id,target_date,hours_per_day,days_per_week],
            area_id=area_id,target_date=target_date,hours=hours_per_day,days=days_per_week,concurso=concurso_info,
            disciplines=disciplinas,weekly=cronograma,strategy=estrategia,filename=file.filename)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar resposta da IA. Tente novamente. Detalhe: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao analisar edital: {str(e)}")


@router.post("/study/programs/import-edital-with-cargo")
async def import_edital_with_cargo(
    request: Request,
    data: dict,
    session_token: Optional[str] = Cookie(None)
):
    """Create study program from a previously analyzed edital, selecting a specific cargo"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    analysis_id = data.get("analysis_id")
    cargo_index = data.get("cargo_index", 0)
    area_id = data.get("area_id")
    target_date = data.get("target_date")
    hours_per_day = data.get("hours_per_day", 4.0)
    days_per_week = data.get("days_per_week", 5)

    if not analysis_id or not area_id:
        raise HTTPException(status_code=400, detail="analysis_id e area_id são obrigatórios")

    await programs.validate_area(user.user_id,area_id,hours_per_day,days_per_week,target_date)

    # Get stored analysis
    analysis = await sql_edital.get(user.user_id,analysis_id,include_source=True)
    if not analysis:
        raise HTTPException(status_code=404, detail="Análise não encontrada. Faça upload do edital novamente.")

    cargos = analysis.get("cargos", [])
    if type(cargo_index) is not int or not cargos or not 0 <= cargo_index < len(cargos):
        raise HTTPException(status_code=400, detail="Cargo inválido")

    selected_cargo = cargos[cargo_index]
    from edital_audit import audit_cargos
    audit_cargos([selected_cargo], analysis.get('pdf_pages', []))
    if selected_cargo.get('conferencia', {}).get('missing'):
        raise HTTPException(status_code=422, detail=selected_cargo['disciplinas_aviso'])
    concurso_info = analysis.get("concurso", {})
    concurso_info["cargo"] = selected_cargo.get("nome", "")
    concurso_info["vagas"] = selected_cargo.get("vagas", "")
    concurso_info["remuneracao"] = selected_cargo.get("remuneracao", "")
    concurso_info["escolaridade"] = selected_cargo.get("escolaridade", "")

    disciplinas = selected_cargo.get("disciplinas", [])
    if needs_disciplines(selected_cargo):
        if analysis.get("analysis_version", 0) < 3:
            raise HTTPException(status_code=422, detail="Esta análise antiga pode ter omitido os anexos. Reenvie o PDF completo e analise novamente.")
        user_api_key = await get_user_api_key(user.user_id)
        if user_api_key:
            try:
                disciplinas = await _hydrate_disciplinas_from_text(
                    edital_context(analysis.get("pdf_text", "")), selected_cargo.get("nome", ""), user_api_key, user.user_id
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            if disciplinas:
                selected_cargo["disciplinas"] = disciplinas
                mark_discipline_quality([selected_cargo])
                await sql_edital.replace_cargo(user.user_id,analysis_id,cargo_index,selected_cargo,analysis['revision'])
    if needs_disciplines(selected_cargo):
        raise HTTPException(status_code=422, detail="Disciplinas incompletas para este cargo. Reanalise o edital antes de criar o programa.")
    disciplinas = selected_cargo["disciplinas"]

    try:
        disc_list = json.dumps(disciplinas, ensure_ascii=False)

        prompt = f"""Gere cronograma para estas disciplinas de concurso: {disc_list}

Configuração do aluno:
- {hours_per_day} horas por dia, {days_per_week} dias por semana
{"- Data da prova: " + target_date if target_date else "- Sem data definida."}

Responda APENAS com JSON:
{{
  "cronograma_semanal": [
    {{
      "dia": "Segunda",
      "frase_motivacional": "Frase motivacional curta para o dia",
      "blocos": [
        {{
          "disciplina": "Nome exato da disciplina",
          "duracao_minutos": 120,
          "tipo_estudo": "Teoria + Questões",
          "prioridade": "alta"
        }}
      ]
    }}
  ],
  "materias_por_dia_sugerido": 3,
  "inclui_redacao": true,
  "ciclo_revisao": "A cada 3 dias, reserve 30-45min para revisão das matérias estudadas nos dias anteriores",
  "estrategia": {{
    "resumo": "Resumo da estratégia geral",
    "fase_1": "Fase 1: Base teórica (primeiros 30% do tempo)",
    "fase_2": "Fase 2: Aprofundamento + questões (40% do tempo)",
    "fase_3": "Fase 3: Revisão intensiva + simulados (30% final)",
    "dicas_gerais": ["Dica 1", "Dica 2", "Dica 3"],
    "materias_prioritarias": ["Matéria de maior peso"],
    "plano_revisao": "Explicação do ciclo de revisão espaçada"
  }}
}}

REGRAS CRÍTICAS:
1. PESOS: Matérias com maior peso devem ter MAIS tempo (proporcional ao peso). Ex: peso 3 = ~3x mais tempo que peso 1
2. REDAÇÃO: Se o concurso exige redação (comum em concursos de nível superior), inclua 1-2 blocos semanais de "Redação" com tipo_estudo "Prática de Redação"
3. REVISÃO: Inclua blocos de "Revisão Geral" a cada 2-3 dias (30-45min) para fixação por repetição espaçada
4. ALTERNÂNCIA: Nunca coloque duas matérias pesadas/densas em sequência - intercale com matérias mais leves
5. MATÉRIAS POR DIA: Sugira 2-4 matérias por dia (ideal 3), nunca mais que 4 para manter foco
6. BLOCOS: Cada bloco entre 45-120min. Intervalos de 10-15min entre blocos (implícito)
7. LIMITE: Máximo {int(hours_per_day * 60)} minutos por dia de estudo efetivo
8. DIAS: Usar apenas {days_per_week} dias. Dias: Segunda, Terça, Quarta, Quinta, Sexta, Sábado, Domingo
9. MOTIVAÇÃO: Cada dia deve ter uma frase motivacional ÚNICA e IMPACTANTE (curta, 1 linha)
10. DESCANSO: Se {days_per_week} < 7, os dias livres são para descanso/lazer
11. CONSISTÊNCIA: O nome da disciplina nos blocos deve ser EXATAMENTE igual ao nome na lista de disciplinas"""

        system_msg = "Você é um MESTRE em planejamento de estudos para concursos públicos brasileiros, com experiência em coaching de aprovados."

        response_text = await call_llm(prompt, f"cronograma_{user.user_id}_{uuid.uuid4().hex[:6]}", system_msg, user_id=user.user_id, task='edital_extract')

        if "Configure sua chave" in response_text:
            raise HTTPException(status_code=500, detail=response_text)

        json_str = response_text.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        parsed = json.loads(json_str.strip())
        cronograma = parsed.get("cronograma_semanal", [])
        estrategia = parsed.get("estrategia", {})

        return await programs.create(user.user_id,request.headers.get('Idempotency-Key'),
            ['import-edital-cargo',data],area_id=area_id,target_date=target_date,hours=hours_per_day,days=days_per_week,
            concurso=concurso_info,disciplines=disciplinas,weekly=cronograma,strategy=estrategia,
            filename=analysis.get('pdf_filename',''),cargo=selected_cargo,analysis_id=analysis_id)

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Erro ao processar resposta da IA. Tente novamente.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar programa: {str(e)}")
