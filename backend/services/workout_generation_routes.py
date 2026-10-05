import os
import json
import uuid
import logging
from datetime import datetime,timezone
from typing import Optional,List,Dict,Any
from fastapi import APIRouter,Request,Cookie,UploadFile,File,HTTPException
from pydantic import BaseModel,Field
from services import workout_plan_writes as sql_plans
from services.study_material_routes import upload_part,read_upload
api_router=APIRouter()
get_current_user=call_llm=get_user_api_key=request_gemini=None

def configure(authenticate,llm,key,gemini):
    global get_current_user,call_llm,get_user_api_key,request_gemini
    get_current_user,call_llm,get_user_api_key,request_gemini=authenticate,llm,key,gemini

class WorkoutPlanGenerate(BaseModel):
    objective: str  # hipertrofia, emagrecimento, condicionamento, forca, flexibilidade
    level: str  # iniciante, intermediario, avancado
    workout_type: str = "musculacao"  # "musculacao", "corrida", "hibrido", "calistenia"
    muscle_groups: Optional[List[str]] = None  # peito, costas, pernas, ombros, biceps, triceps, abdomen, gluteos, trapezio, antebraco, panturrilha
    duration: str = "dia"  # dia, semana, mes, ciclo
    # New fields for split-based generation
    generation_mode: str = "periodo"  # "periodo" or "tipo_treino"
    split_type: Optional[str] = None  # "AB", "ABC", "ABCD", "ABCDE"
    split_config: Optional[List[Dict[str, Any]]] = None  # [{label: "A", name: "Peito e Tríceps", muscle_groups: ["peito", "triceps"]}]
    training_days_per_week: Optional[int] = Field(default=None, ge=2, le=7)  # 2-7
    cycle_weeks: Optional[int] = Field(default=None, ge=1, le=12)  # 1-12
    include_cardio: bool = False
    cardio_type: Optional[str] = None  # "corrida", "bike", "HIIT", "caminhada", "natacao", "pular_corda"
    cardio_mode: Optional[str] = None  # "hibrido", "hibrido_alternado"
    health_condition: Optional[str] = None  # user health conditions/injuries to consider
    # Running-specific fields
    running_goal: Optional[str] = None  # "5km", "10km", "meia_maratona", "maratona", "condicionamento", "emagrecimento"
    weekly_frequency: Optional[int] = Field(default=None, ge=2, le=7)  # 2-7 days per week
    preferred_terrain: Optional[str] = None  # "asfalto", "esteira", "trilha", "misto"
    # Calisthenics-specific fields
    calisthenics_focus: Optional[str] = None  # "forca_upper", "forca_lower", "full_body", "habilidades", "condicionamento"
    calisthenics_equipment: Optional[str] = None  # "barra", "paralelas", "argolas", "solo", "nenhum"


@api_router.post("/workout-plans/generate")
async def generate_workout_plan(request: Request, gen_data: WorkoutPlanGenerate, session_token: Optional[str] = Cookie(None)):
    """Generate a workout plan with AI including tutorials and YouTube video links"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    # Build health condition text if provided
    health_text = ""
    if gen_data.health_condition and gen_data.health_condition.strip():
        health_text = f"""
CONDIÇÃO DE SAÚDE / LESÕES DO USUÁRIO:
{gen_data.health_condition.strip()}

ATENÇÃO: Adapte TODOS os exercícios considerando esta condição. Evite exercícios que possam agravar a lesão/condição.
Inclua exercícios de fortalecimento e reabilitação quando apropriado.
Para cada exercício, adicione um campo "health_notes" com observações específicas sobre como adaptar o exercício à condição do usuário.
Se algum exercício for contraindicado, substitua por uma alternativa segura e explique por quê.
"""
        # Save health condition to user profile for future use
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"health_condition": gen_data.health_condition.strip()}}
        )

    # ===== BUILD PROMPT BASED ON WORKOUT TYPE =====
    if gen_data.workout_type in ("corrida",):
        # --- RUNNING-ONLY WORKOUT ---
        goal_labels = {
            "5km": "Completar 5km", "10km": "Completar 10km",
            "meia_maratona": "Meia Maratona (21km)", "maratona": "Maratona (42km)",
            "condicionamento": "Condicionamento cardiovascular", "emagrecimento": "Emagrecimento"
        }
        goal_text = goal_labels.get(gen_data.running_goal or "", gen_data.running_goal or "Condicionamento")
        freq = gen_data.weekly_frequency or 4
        terrain = gen_data.preferred_terrain or "asfalto"
        duration_map = {"dia": "um dia", "semana": "uma semana", "mes": "um mês", "ciclo": "um ciclo (8-12 semanas)"}
        dur_text = duration_map.get(gen_data.duration, gen_data.duration)

        prompt = f"""Você é um coach de corrida certificado. Gere um plano de treino de corrida completo em formato JSON.

PARÂMETROS:
- Objetivo: {goal_text}
- Nível do corredor: {gen_data.level}
- Duração: {dur_text}
- Frequência semanal: {freq} dias/semana
- Terreno preferido: {terrain} (asfalto, esteira, trilha ou misto)
{health_text}

ORIENTAÇÕES:
- Varie os tipos de treino ao longo da semana: rodagem leve (zona 2), tiros/intervalado, tempo run, longão.
- Inclua aquecimento (5-10min caminhada + alongamento dinâmico) e desaquecimento (5min caminhada + alongamento estático).
- Para PLANO DIÁRIO: 1 dia de treino apenas.
- Para PLANO SEMANAL: organize {freq} dias na semana (segunda a domingo). Alterne dias de corrida com descanso ativo (caminhada, mobilidade).
- Para PLANO MENSAL: 4 semanas com progressão de volume (aumento semanal de ~10% no km total).
- Para CICLO: periodização em fases: Base aeróbica (2-3sem), Construção (3-4sem), Pico (2sem), Polimento/Descanso (1sem).

Para CADA exercício (treino do dia), inclua:
  - "name": nome do treino (ex: "Rodagem Leve Zona 2", "Tiros 400m", "Tempo Run", "Longão", "Descanso Ativo")
  - "sets": 1 (para treinos baseados em tempo/distância)
  - "reps": duração em minutos ou distância (ex: "30min", "5km", "60min")
  - "weight": zona de intensidade ou pace (ex: "Z2 - Conversacional", "Ritmo de prova", "Pace 5:30/km")
  - "rest_seconds": 0 (corrida não tem descanso entre séries; o descanso é entre dias)
  - "muscle_group": "cardio"
  - "tutorial": instruções detalhadas do treino: como executar, pace sugerido, FC alvo, percepção de esforço (PSE), dicas de respiração e postura

FORMATO JSON OBRIGATÓRIO:
{{
  "name": "Plano de Corrida - {goal_text}",
  "description": "Descrição breve do plano",
  "plan_duration": "{gen_data.duration}",
  "days": [
    {{
      "day_name": "dia1",
      "day_label": "Segunda - Rodagem Leve",
      "exercises": [
        {{
          "name": "Aquecimento",
          "sets": 1, "reps": "10min", "weight": "Caminhada leve",
          "rest_seconds": 0, "muscle_group": "cardio",
          "tutorial": "Caminhe em ritmo leve por 10 minutos. Alongamento dinâmico: elevação de joelhos, calcanhar ao glúteo, passada lateral."
        }},
        {{
          "name": "Rodagem Leve Zona 2",
          "sets": 1, "reps": "30min", "weight": "Z2 - Conversacional",
          "rest_seconds": 0, "muscle_group": "cardio",
          "tutorial": "Corra em ritmo confortável onde consegue manter uma conversa. FC entre 60-70% da FC máxima. Respiração nasal. Postura ereta, braços relaxados, passadas curtas e rápidas."
        }},
        {{
          "name": "Desaquecimento",
          "sets": 1, "reps": "5min", "weight": "Caminhada leve + alongamento",
          "rest_seconds": 0, "muscle_group": "cardio",
          "tutorial": "Reduza o ritmo gradualmente até caminhar. Alongue panturrilhas, quadríceps, isquiotibiais e glúteos por 20-30 segundos cada."
        }}
      ]
    }}
  ]
}}

REGRAS:
- Retorne APENAS JSON válido, sem markdown, sem texto extra.
- Adapte volume e intensidade ao nível ({gen_data.level}).
- {freq} dias de treino por semana, com intensidades variadas.
- Siga o princípio de progressão gradual (não mais que 10% de aumento semanal)."""

    elif gen_data.workout_type in ("calistenia",) and gen_data.generation_mode == "periodo":
        # --- CALISTHENICS (PERIOD MODE) ---
        focus_labels = {
            "forca_upper": "Força de Upper Body", "forca_lower": "Força de Lower Body",
            "full_body": "Full Body", "habilidades": "Habilidades Calistênicas (handstand, muscle-up, front lever, back lever, planche)",
            "condicionamento": "Condicionamento Calistênico"
        }
        focus_text = focus_labels.get(gen_data.calisthenics_focus or "", gen_data.calisthenics_focus or "Full Body")
        equip_labels = {
            "barra": "Barra Fixa", "paralelas": "Barras Paralelas",
            "argolas": "Argolas", "solo": "Solo (apenas chão)", "nenhum": "Nenhum (só peso corporal)"
        }
        equip_text = equip_labels.get(gen_data.calisthenics_equipment or "", gen_data.calisthenics_equipment or "Nenhum")
        dur_label_map = {"dia": "um dia", "semana": "uma semana", "mes": "um mês", "ciclo": "um ciclo (8-12 semanas)"}
        dur_text = dur_label_map.get(gen_data.duration, gen_data.duration)

        prompt = f"""Você é um coach de calistenia certificado. Gere um plano de treino APENAS com exercícios de calistenia (peso corporal e/ou barra fixa/paralelas/argolas) em formato JSON.

PARÂMETROS:
- Foco: {focus_text}
- Nível do aluno: {gen_data.level}
- Duração do plano: {dur_text}
- Equipamento disponível: {equip_text}
- Objetivo principal: {gen_data.objective}
{health_text}

ORIENTAÇÕES TÉCNICAS DE CALISTENIA:
- Use APENAS exercícios de peso corporal, barra fixa, barras paralelas, argolas ou solo.
- SISTEMA DE PROGRESSÕES: para cada movimento, indique a progressão adequada ao nível:
  * Iniciante: versões simplificadas (flexão de joelhos, barra australiana, agachamento ar, pike push-up)
  * Intermediário: versões clássicas (flexão completa, barra fixa, agachamento búlgaro, paralela)
  * Avançado: versões avançadas (flexão diamante/archer, barra explosiva/muscle-up progressão, pistols, L-sit, handstand push-up)
- Inclua progressão de sobrecarga via: aumento de reps, diminuição de descanso, variação de alavanca (ângulo mais difícil), adição de tempo sob tensão (isometria).
- Para HABILIDADES (handstand, front lever, back lever, planche, L-sit, muscle-up): inclua drills preparatórios, progressões semanais e tempo de prática de habilidade (ex: "Prática de Handstand contra parede 10-15min").
- Estruture cada treino com: aquecimento específico + ativação + trabalho principal + core/finalizador + alongamento.
- Repetições baseadas em falha técnica (parar quando a forma começar a quebrar) ou range definido.
- DESCANSO: 60-90s entre séries de força, 90-120s para séries de falha.

Para CADA exercício no JSON:
  - "name": nome do exercício + progressão (ex: "Flexão Completa", "Barra Fixa Pronada", "Agachamento Búlgaro", "Paralela", "Prancha", "L-Sit Hold", "Handstand Walk")
  - "sets": número de séries
  - "reps": número de repetições OU "AMRAP" (para falha) OU tempo em segundos (para isometria)
  - "weight": nível da progressão (ex: "Completa", "Joelhos", "Assistida com elástico", "Negativa", "Explosiva", "Archer")
  - "rest_seconds": descanso em segundos entre séries (60-120)
  - "muscle_group": grupo muscular primário (peito, costas, pernas, ombros, core, braços, full_body, cardiorespiratorio)
  - "tutorial": instruções detalhadas de execução: posição inicial, movimento, respiração, erros comuns, dica de progressão/regressão, e tempo de prática sugerido para habilidades

FORMATO JSON OBRIGATÓRIO:
{{
  "name": "Treino Calistenia - {focus_text}",
  "description": "Descrição breve do plano",
  "plan_duration": "{gen_data.duration}",
  "days": [
    {{
      "day_name": "dia1",
      "day_label": "Treino A - Empurrar",
      "exercises": [
        {{
          "name": "Aquecimento Articular",
          "sets": 1, "reps": "8-10min", "weight": "Mobilidade dinâmica",
          "rest_seconds": 0, "muscle_group": "full_body",
          "tutorial": "Círculos de braço, rotação de punhos, ombros e quadril, cat-cow, leg swings. 8-10 minutos."
        }},
        {{
          "name": "Flexão Completa",
          "sets": 4, "reps": 10, "weight": "Padrão",
          "rest_seconds": 90, "muscle_group": "peito",
          "tutorial": "Mãos na largura dos ombros, corpo reto da cabeça ao calcanhar. Desça até o peito tocar o chão (ou cotovelos a 90°). Expire ao subir. Mantenha core contraído. Variação mais fácil: joelhos no chão. Variação mais difícil: pés elevados."
        }},
        {{
          "name": "Paralela",
          "sets": 3, "reps": 8, "weight": "Completa",
          "rest_seconds": 90, "muscle_group": "triceps",
          "tutorial": "Entre barras paralelas, corpo ereto. Desça até cotovelos a 90°, suba com força. Mantenha ombros estáveis (sem encolher). Variação fácil: assistida com elástico. Variação difícil: com peso adicional ou L-sit."
        }},
        {{
          "name": "Prancha",
          "sets": 3, "reps": "45s", "weight": "Padrão",
          "rest_seconds": 60, "muscle_group": "core",
          "tutorial": "Antebraços no chão, cotovelos sob os ombros. Corpo em linha reta. Contraia glúteos e abdômen. Respiração contínua. Variação fácil: joelhos no chão. Variação difícil: elevar uma perna."
        }}
      ]
    }}
  ]
}}

REGRAS:
- Retorne APENAS JSON válido, sem markdown, sem texto extra.
- Adapte volume e intensidade ao nível ({gen_data.level}).
- Varie os estímulos nos dias da semana (push/pull/legs ou full body).
- {equip_text} -- use apenas exercícios compatíveis com este equipamento.
- Para {focus_text}: foque o plano neste tema.
- Para plano semanal/mensal: alterne estímulos e inclua progressão semanal explícita.
- Siga o princípio de progressão gradual (não mais que 10% de aumento semanal)."""

    elif gen_data.generation_mode == "tipo_treino" and gen_data.split_config:
        # --- SPLIT-BASED GENERATION (Tipo de Treino) ---
        # Strategy: Generate only BASE SPLITS (A, B, C...) + weekly progression notes
        # Then expand to full days on the server side to avoid huge AI responses
        split_description = []
        for split in gen_data.split_config:
            label = split.get("label", "?")
            name = split.get("name", "")
            groups = split.get("muscle_groups", [])
            split_description.append(f"  Treino {label}: {name} (Grupos: {', '.join(groups)})")
        split_text = "\n".join(split_description)

        days_per_week = gen_data.training_days_per_week or 5
        cycle_weeks = gen_data.cycle_weeks or 4
        split_type = gen_data.split_type or "ABC"
        split_labels = [s.get("label", "") for s in gen_data.split_config]

        cardio_text = ""
        if gen_data.include_cardio:
            cardio_name = gen_data.cardio_type or "corrida"
            cardio_labels = {
                "corrida": "Corrida", "bike": "Bike/Ciclismo", "HIIT": "HIIT",
                "caminhada": "Caminhada", "natacao": "Natação", "pular_corda": "Pular Corda",
                "eliptico": "Elíptico", "remo": "Remo"
            }
            cardio_display = cardio_labels.get(cardio_name, cardio_name)
            cardio_mode = gen_data.cardio_mode or "hibrido"

            if cardio_mode == "hibrido":
                cardio_text = f"""
TREINO HÍBRIDO (Musculação + Cardio no mesmo dia):
- NÃO crie split separada de cardio.
- Em CADA split de musculação, adicione 2-3 exercícios de cardio ({cardio_display}) ao FINAL da lista de exercícios.
- Estes exercícios finais devem ter muscle_group: "cardio" e seguir o formato padrão.
- Varie a intensidade do cardio entre os dias: em um split use cardio de alta intensidade (tiros, HIIT), em outro use cardio de baixa/moderada intensidade (zona 2, ritmo constante).
- Exemplo alta intensidade: {{"name": "{cardio_display} - Tiros (HIIT)", "sets": 1, "reps": "15-20min", "rest_seconds": 0, "muscle_group": "cardio", "tutorial": "Alterne 30seg de alta intensidade com 60seg de recuperação. Total 15-20 minutos."}}
- Exemplo baixa intensidade: {{"name": "{cardio_display} - Zona 2 (moderado)", "sets": 1, "reps": "20-30min", "rest_seconds": 0, "muscle_group": "cardio", "tutorial": "Mantenha ritmo constante e confortável, onde consiga conversar. Frequência cardíaca em zona 2."}}
- O ÚLTIMO dia da semana deve ser um dia de DESCANSO (split_label: "Descanso", com exercícios leves ou nenhum exercício).
"""
            elif cardio_mode == "hibrido_alternado":
                cardio_text = f"""
TREINO HÍBRIDO ALTERNADO (1 dia musculação, 1 dia cardio):
- Adicione um item extra no array "splits" com split_label: "Cardio", split_name: "{cardio_display}".
- O cardio DEVE usar o mesmo formato "exercises": name, sets (1), reps (duração), rest_seconds, muscle_group ("cardio"), tutorial.
- VARIE a intensidade do cardio entre os dias: alterne entre alta intensidade (tiros/HIIT) e baixa/moderada intensidade (zona 2).
- Inclua 4-5 exercícios por dia de cardio: aquecimento, blocos de intensidade variada, desaquecimento.
- Exemplo para dia de alta intensidade: {{"name": "{cardio_display} - Tiros", "sets": 1, "reps": "30seg sprint + 60seg descanso x8", "rest_seconds": 0, "muscle_group": "cardio", "tutorial": "Sprint máximo por 30 segundos, descanse 60 segundos caminhando. Repita 8 vezes."}}
- Exemplo para dia de zona 2: {{"name": "{cardio_display} - Zona 2", "sets": 1, "reps": "30-40min", "rest_seconds": 0, "muscle_group": "cardio", "tutorial": "Ritmo constante onde consegue manter uma conversa. Foco em resistência aeróbica."}}
- O ÚLTIMO dia da semana DEVE ser de DESCANSO absoluto ou ativo (caminhada leve de 20-30min). Use split_label: "Descanso".
- Padrão ideal: Seg musculação, Ter cardio alta intensidade, Qua musculação, Qui cardio zona 2, Sex musculação, Sáb cardio moderado, Dom descanso.
"""

        prompt = f"""Você é um personal trainer certificado. Gere APENAS os treinos BASE de cada divisão ({split_type}) em formato JSON compacto.

NÃO gere todos os dias do ciclo. Gere apenas 1 treino para cada letra da divisão + notas de progressão semanal.

PARÂMETROS:
- Objetivo: {gen_data.objective}
- Nível: {gen_data.level}
- Divisão: {split_type} ({len(split_labels)} treinos base)
- Ciclo: {cycle_weeks} semana(s), {days_per_week} dias/semana
{health_text}
DIVISÕES:
{split_text}
{cardio_text}

FORMATO JSON OBRIGATÓRIO:
{{
  "name": "Treino {split_type} - {gen_data.objective.capitalize()}",
  "description": "Descrição breve",
  "plan_duration": "ciclo",
  "split_type": "{split_type}",
  "cycle_weeks": {cycle_weeks},
  "training_days_per_week": {days_per_week},
  "splits": [
    {{
      "split_label": "A",
      "split_name": "Peito e Tríceps",
      "exercises": [
        {{
          "name": "Supino Reto",
          "sets": 4,
          "reps": 10,
          "weight": "adequado",
          "rest_seconds": 90,
          "muscle_group": "peito",
          "tutorial": "Instrução concisa de execução em 1-2 frases."
        }}
      ]
    }}
  ],
  "weekly_progression": [
    {{
      "week": 1,
      "focus": "Adaptação e técnica",
      "notes": "Carga moderada, foco na execução correta"
    }},
    {{
      "week": 2,
      "focus": "Aumento de volume",
      "notes": "Aumente 1-2 reps por exercício"
    }}
  ]
}}

REGRAS:
- Retorne APENAS JSON válido, sem markdown, sem texto extra.
- Gere 1 treino por letra ({', '.join(split_labels)}).
- Tutorial: máximo 2 frases curtas por exercício.
- {len(split_labels) * 5} a {len(split_labels) * 7} exercícios no total (4-6 por split para iniciante, 5-7 intermediário, 6-8 avançado).
- Gere {cycle_weeks} itens em weekly_progression.
- rest_seconds: 60s leves, 90s moderados, 120s compostos pesados."""

    else:
        # --- PERIOD-BASED GENERATION (existing flow) ---
        duration_instructions = {
            "dia": "Crie um treino para UM DIA ÚNICO. Liste os exercícios em um único bloco.",
            "semana": "Crie um treino para UMA SEMANA COMPLETA (segunda a sexta, 5 dias). Organize por dia da semana com exercícios diferentes para cada dia, alternando grupos musculares.",
            "mes": "Crie um plano de treino para UM MÊS (4 semanas). Organize em 4 semanas com progressão de carga/volume. Cada semana deve ter 5 dias de treino.",
            "ciclo": "Crie um ciclo de treino periodizado (8-12 semanas). Organize em fases: Adaptação (2 semanas), Hipertrofia (4 semanas), Força (3 semanas), Deload (1 semana). Cada fase com treinos específicos."
        }

        muscle_groups_text = ""
        if gen_data.muscle_groups and len(gen_data.muscle_groups) > 0:
            muscle_groups_text = f"\nGrupos musculares prioritários: {', '.join(gen_data.muscle_groups)}"

        prompt = f"""Você é um personal trainer certificado. Gere um plano de treino completo em formato JSON.

PARÂMETROS:
- Objetivo: {gen_data.objective}
- Nível: {gen_data.level}
- Duração: {gen_data.duration}{muscle_groups_text}
{health_text}
{duration_instructions.get(gen_data.duration, duration_instructions['dia'])}

Para CADA exercício, inclua um tutorial descritivo de execução em 1-2 frases curtas.

FORMATO JSON OBRIGATÓRIO:
{{
  "name": "Nome do plano de treino",
  "description": "Descrição breve do objetivo",
  "plan_duration": "{gen_data.duration}",
  "days": [
    {{
      "day_name": "dia1",
      "day_label": "Segunda - Peito e Tríceps",
      "exercises": [
        {{
          "name": "Supino Reto com Barra",
          "sets": 4,
          "reps": 10,
          "weight": "adequado ao nível",
          "rest_seconds": 90,
          "muscle_group": "peito",
          "tutorial": "Deite no banco, desça a barra ao peito controladamente e empurre para cima. Inspire ao descer, expire ao subir."
        }}
      ]
    }}
  ]
}}

{"Retorne apenas 1 dia no array 'days'." if gen_data.duration == "dia" else ""}
{"Retorne 5 dias (seg-sex) no array 'days'." if gen_data.duration == "semana" else ""}
{"Organize semanas: dias como 'sem1_dia1', 'sem1_dia2', etc." if gen_data.duration == "mes" else ""}
{"Organize por fases: dias como 'fase1_sem1_dia1', etc." if gen_data.duration == "ciclo" else ""}

IMPORTANTE:
- Retorne APENAS JSON válido, sem markdown, sem texto extra.
- Tutorial: máximo 2 frases curtas por exercício.
- Adapte ao nível ({gen_data.level}).
- rest_seconds: 60s leves, 90s moderados, 120s compostos pesados."""

    # Helper to clean and parse JSON from AI response
    def _clean_and_parse_json(text: str) -> dict:
        """Robustly clean and parse JSON from AI response text"""
        import re
        cleaned = text.strip()
        # Remove markdown code blocks
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        # Remove any trailing text after the last }
        last_brace = cleaned.rfind("}")
        if last_brace != -1 and last_brace < len(cleaned) - 1:
            cleaned = cleaned[:last_brace + 1]
        # Try to find JSON object if there's leading text
        first_brace = cleaned.find("{")
        if first_brace > 0:
            cleaned = cleaned[first_brace:]
        # Fix common JSON issues: trailing commas before } or ]
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        return json.loads(cleaned)

    from workout_calendar import calendar_shape, validate_ai_calendar, normalize_days, expand_splits
    if gen_data.workout_type == "corrida":
        gen_data.generation_mode = "periodo"
    try:
        expected_weeks, expected_frequency = calendar_shape(gen_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    contract = f"\nCALENDÁRIO OBRIGATÓRIO: {expected_weeks} semanas, {expected_frequency} dias por semana, {expected_weeks * expected_frequency} dias no total."
    if gen_data.generation_mode == "tipo_treino":
        contract += " Retorne splits completos para todas as divisões solicitadas; o servidor expandir? o calendário."
    else:
        contract += " Retorne TODOS os dias em days, ordenados por semana e dia, com week inteiro a partir de 1 e day_name semN_diaN. Não resuma nem omita semanas."
    prompt += contract
    plan_data = None
    response_text = ""
    try:
        # One corrective attempt for incomplete or malformed responses; no partial plan is saved.
        correction = ""
        for attempt in range(2):
            response_text = await call_llm(
                prompt + correction + "\nResponda APENAS com JSON puro, sem markdown, sem texto extra.",
                f"workout_{user.user_id}",
                "Voc? ? um personal trainer profissional certificado. Sempre responda SOMENTE em JSON válido, sem nenhum texto adicional.",
                user_id=user.user_id
            , task='workout_generation')
            if response_text and response_text.startswith("?"):
                raise HTTPException(status_code=502, detail=response_text)
            try:
                plan_data = validate_ai_calendar(_clean_and_parse_json(response_text or ""), gen_data)
                break
            except (ValueError, TypeError) as exc:
                if attempt == 1:
                    raise HTTPException(status_code=502, detail="A IA não retornou um calendário completo e consistente. Nenhum treino foi salvo. Tente gerar novamente.")
                correction = f"\nA resposta anterior estava incompleta ou inválida: {exc}. Gere novamente o JSON completo respeitando o calendário obrigatório."

        logging.info("Successfully parsed workout plan")

    except json.JSONDecodeError as e:
        logging.error(f"JSON parse error: {e}")
        logging.error(f"Response text (first 500 chars): {response_text[:500] if response_text else 'N/A'}")
        raise HTTPException(status_code=500, detail="Erro ao processar resposta da IA. Tente novamente.")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Workout generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar treino: {str(e)}. Tente novamente.")

    try:
        # Create the plan document
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"

        # For tipo_treino: expand splits into days on the server side
        days = []
        weekly_progression = plan_data.get("weekly_progression", [])

        if gen_data.generation_mode == "tipo_treino" and plan_data.get("splits"):
            days = expand_splits(plan_data, gen_data)
        else:
            # Period-based: days come directly from AI response
            days = plan_data.get("days", [])

        days = normalize_days(days, expected_weeks, expected_frequency)

        # Flatten exercises for backward compatibility
        all_exercises = []
        for day in days:
            for ex in day.get("exercises", []):
                all_exercises.append(ex)

        # Determine plan_duration
        plan_duration = gen_data.duration
        if gen_data.generation_mode == "tipo_treino":
            plan_duration = "ciclo"

        plan_doc = {
            "plan_id": plan_id,
            "user_id": user.user_id,
            "name": plan_data.get("name", f"Treino {gen_data.objective} - {gen_data.level}"),
            "description": plan_data.get("description", ""),
            "exercises": all_exercises,
            "plan_duration": plan_duration,
            "generated_by_ai": True,
            "days": days,
            "weekly_progression": weekly_progression,
            "workout_type": gen_data.workout_type,
            "objective": gen_data.objective,
            "level": gen_data.level,
            "generation_mode": gen_data.generation_mode,
            "split_type": gen_data.split_type if gen_data.generation_mode == "tipo_treino" else None,
            "split_config": gen_data.split_config if gen_data.generation_mode == "tipo_treino" else None,
            "training_days_per_week": expected_frequency,
            "cycle_weeks": expected_weeks,
            "include_cardio": gen_data.include_cardio if gen_data.generation_mode == "tipo_treino" else False,
            "cardio_type": gen_data.cardio_type if gen_data.generation_mode == "tipo_treino" and gen_data.include_cardio else None,
            "cardio_mode": gen_data.cardio_mode if gen_data.generation_mode == "tipo_treino" and gen_data.include_cardio else None,
            "health_condition": gen_data.health_condition if gen_data.health_condition else None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        return await sql_plans.save(user.user_id,request.headers.get('Idempotency-Key'),
            ['generate-workout-plan',gen_data.model_dump(mode='json')],plan_doc,5)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to save workout plan: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar treino: {str(e)[:100]}")


@api_router.post("/workouts/import-plan")
async def import_workout_plan(
    request: Request,
    file: UploadFile = File(...),
    session_token: Optional[str] = Cookie(None)
):
    """Import a workout plan from PDF or image using AI extraction"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    if not await get_user_api_key(user.user_id):
        raise HTTPException(status_code=500, detail="Serviço de IA indisponível")

    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Limite de 20MB.")

    try:
        part = await upload_part(content,file.filename,file.content_type,user.user_id)

        system_msg = """Analise esta ficha de treino e extraia TODOS os exercícios.
Responda APENAS com JSON:
{
  "name": "Nome do Treino (ex: Treino A - Peito/Tríceps)",
  "description": "Descrição breve",
  "exercises": [
    {"name": "Nome do exercício", "sets": 3, "reps": "12", "weight": "10kg", "notes": "Observações"}
  ]
}
REGRAS: Extraia TODOS os exercícios fielmente. Se não conseguir ler algo, indique com [ilegível]."""

        response = await request_gemini(task='workout_generation', contents=[part, 'Extraia a ficha de treino deste documento:'], config=dict(system_instruction=system_msg), user_id=user.user_id)

        json_str = response.text.strip()
        if json_str.startswith("```json"): json_str = json_str[7:]
        if json_str.startswith("```"): json_str = json_str[3:]
        if json_str.endswith("```"): json_str = json_str[:-3]
        plan_data = json.loads(json_str.strip())

        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        plan_doc = {
            "plan_id": plan_id,
            "user_id": user.user_id,
            "name": plan_data.get("name", f"Treino importado - {file.filename}"),
            "description": plan_data.get("description", "Importado via arquivo"),
            "exercises": plan_data.get("exercises", []),
            "source": "file_import",
            "source_filename": file.filename,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        import hashlib
        result=await sql_plans.save(user.user_id,request.headers.get('Idempotency-Key'),
            ['import-workout-plan',file.filename,hashlib.sha256(content).hexdigest()],plan_doc,10)
        return {**result,'message':f"Treino importado com {len(result['plan']['exercises'])} exercicios!"}

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Erro ao processar ficha de treino. Tente novamente.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

