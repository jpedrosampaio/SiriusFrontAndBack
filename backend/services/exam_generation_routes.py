"""Existing exam AI prompts with owned SQL persistence."""
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter,Cookie,File,Form,HTTPException,Request,UploadFile
from pydantic import BaseModel,Field
from services import exam_catalog as catalog

router=APIRouter()


def configure(authenticate,key,generate,upload,file_part):
    global get_current_user,get_user_api_key,request_gemini,upload_gemini_path,gemini_file_part
    get_current_user,get_user_api_key,request_gemini,upload_gemini_path,gemini_file_part=authenticate,key,generate,upload,file_part

class SimuladoCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    banca: Optional[str] = None  # CESPE, FCC, VUNESP, FGV, etc.
    disciplina: Optional[str] = None  # Direito, Português, Matemática, etc.
    concurso: Optional[str] = None  # TRF, TJ, Receita Federal, etc.
    question_type: str = "multipla_escolha"  # multipla_escolha, certo_errado, misto
    num_questions: int = Field(default=10, ge=1, le=100)
    difficulty: str = "medio"  # facil, medio, dificil, misto
    area_id: Optional[str] = None
    program_id: Optional[str] = None
    notebook_id: Optional[str] = None
    topic_key: Optional[str] = Field(default=None, pattern=r'^\d+(?:_\d+)?$')
    topic: Optional[str] = Field(default=None, max_length=500)


@router.post("/study/simulados/import-pdf")
async def import_simulado_pdf(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form("Simulado Importado"),
    banca: Optional[str] = Form(None),
    disciplina: Optional[str] = Form(None),
    concurso: Optional[str] = Form(None),
    question_type: str = Form("multipla_escolha"),
    area_id: Optional[str] = Form(None),
    program_id: Optional[str] = Form(None),
    session_token: Optional[str] = Cookie(None)
):
    """Import a PDF with questions/answer sheet and create a simulado"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    await catalog.validate_scope(user.user_id,area_id=area_id,program_id=program_id)

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos")

    content = await file.read(20*1024*1024+1)

    if len(content) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Limite de 20MB.")

    tmp_path = None
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        uploaded_file = await upload_gemini_path(tmp_path, user.user_id)

        type_instruction = ""
        if question_type == "multipla_escolha":
            type_instruction = """Cada questão DEVE ter exatamente 5 alternativas (A, B, C, D, E).
O campo "correct_answer" deve ser a LETRA da alternativa correta (ex: "A", "B", "C", "D" ou "E")."""
        elif question_type == "certo_errado":
            type_instruction = """Cada questão é do tipo CERTO ou ERRADO.
O campo "options" deve ser ["Certo", "Errado"].
O campo "correct_answer" deve ser "Certo" ou "Errado"."""
        else:
            type_instruction = """As questões podem ser de múltipla escolha (5 alternativas A-E) ou certo/errado.
Para múltipla escolha: options com 5 alternativas, correct_answer = letra (A-E).
Para certo/errado: options = ["Certo", "Errado"], correct_answer = "Certo" ou "Errado".
Adicione o campo "type": "multipla_escolha" ou "certo_errado" em cada questão."""

        system_msg = f"""Você é um especialista em extrair questões de provas e concursos de documentos PDF.
Sua tarefa é analisar o documento e extrair TODAS as questões encontradas, incluindo TEXTOS BASE / TEXTOS DE APOIO.
{type_instruction}

REGRAS:
- Extraia TODAS as questões do documento, sem pular nenhuma
- Se houver gabarito no documento, use-o para determinar a resposta correta
- Se não houver gabarito, analise e determine a resposta correta
- Mantenha a numeração original das questões
- Preserve o texto completo de cada questão e alternativas
- Se possível, identifique a disciplina/matéria de cada questão
- Adicione uma breve explicação para cada resposta correta

TEXTOS BASE / TEXTOS DE APOIO (MUITO IMPORTANTE):
- Muitas questões de provas (especialmente de Língua Portuguesa, interpretação de texto, legislação, etc.) possuem um TEXTO BASE (texto de apoio, trecho, fragmento, excerto, poema, etc.) que precede as questões
- O texto base é um trecho ou passagem que o candidato precisa ler para responder as questões relacionadas
- Exemplos de cabeçalhos de texto base: "Texto para as questões X a Y", "Leia o texto a seguir", "Com base no texto abaixo", "Texto I", "Texto II", etc.
- EXTRAIA INTEGRALMENTE o texto base associado a cada questão no campo "texto_base"
- Se várias questões se referem ao MESMO texto base, REPITA o texto base completo em CADA uma dessas questões
- Se a questão NÃO possui texto base, deixe o campo "texto_base" como null ou string vazia ""
- O campo "texto_base" deve conter APENAS o texto de apoio, NÃO o enunciado da questão em si
- Preserve a formatação original do texto base (parágrafos, versos de poemas, citações, etc.)

Responda APENAS com um JSON válido no formato:
{{
  "questions": [
    {{
      "question_number": 1,
      "texto_base": "Texto de apoio completo que precede a questão, se houver. Null se não houver.",
      "question_text": "Texto completo do enunciado da questão (sem o texto base)",
      "options": ["A) texto", "B) texto", "C) texto", "D) texto", "E) texto"],
      "correct_answer": "A",
      "explanation": "Breve explicação",
      "disciplina": "Matéria identificada",
      "type": "multipla_escolha"
    }}
  ],
  "metadata": {{
    "total_questions": 10,
    "banca_detected": "Nome da banca se identificada",
    "concurso_detected": "Nome do concurso se identificado",
    "year_detected": "Ano da prova se identificado"
  }}
}}"""

        response = await request_gemini(task='study_question_generation', contents=[gemini_file_part(file_uri=uploaded_file.uri, mime_type='application/pdf'), 'Extraia todas as questões deste documento de prova/simulado e retorne em JSON:'], config=dict(system_instruction=system_msg), user_id=user.user_id)

        # Clean up temp file
        os.unlink(tmp_path)

        # Parse JSON response
        json_str = response.text.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        parsed = json.loads(json_str.strip())
        questions = parsed.get("questions", [])
        metadata = parsed.get("metadata", {})

        if not questions:
            raise HTTPException(status_code=400, detail="Não foi possível extrair questões do PDF. Verifique se o documento contém questões válidas.")

        # Use detected metadata if user didn't provide
        final_banca = banca or metadata.get("banca_detected")
        final_concurso = concurso or metadata.get("concurso_detected")

        simulado_id = f"sim_{uuid.uuid4().hex[:12]}"
        simulado_doc = {
            "simulado_id": simulado_id,
            "user_id": user.user_id,
            "title": title,
            "description": f"Importado de: {file.filename}",
            "source_type": "pdf_import",
            "banca": final_banca,
            "disciplina": disciplina,
            "concurso": final_concurso,
            "question_type": question_type,
            "difficulty": "misto",
            "questions": questions,
            "questions_count": len(questions),
            "area_id": area_id,
            "program_id": program_id,
            "pdf_filename": file.filename,
            "year_detected": metadata.get("year_detected"),
            "status": "ready",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        return await catalog.create(user.user_id,request.headers.get('Idempotency-Key'),
            ['import-simulado',hashlib.sha256(content).hexdigest(),title,banca,disciplina,concurso,question_type,area_id,program_id],simulado_doc,questions)

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse PDF questions JSON: {e}")
        raise HTTPException(status_code=500, detail="Erro ao interpretar as questões do PDF. Tente novamente.")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PDF simulado import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar PDF: {str(e)}")

    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@router.post("/study/simulados/generate")
async def generate_simulado(request: Request, data: SimuladoCreate, session_token: Optional[str] = Cookie(None)):
    """Generate a simulado with AI based on banca/disciplina/concurso"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    notebook,topic = await catalog.validate_scope(user.user_id,area_id=data.area_id,program_id=data.program_id,
        notebook_id=data.notebook_id,topic_key=data.topic_key)
    if notebook:
        data.program_id,data.area_id=notebook.get('program_id'),notebook.get('area_id')
        data.disciplina=notebook['name']
        if topic: data.topic=topic

    if not await get_user_api_key(user.user_id):
        raise HTTPException(status_code=500, detail="Serviço de IA indisponível")

    num_q = data.num_questions

    type_instruction = ""
    if data.question_type == "multipla_escolha":
        type_instruction = """Todas as questões devem ser de MÚLTIPLA ESCOLHA com exatamente 5 alternativas (A, B, C, D, E).
O campo "correct_answer" deve ser a LETRA da alternativa correta (ex: "A", "B", "C", "D" ou "E").
O campo "type" deve ser "multipla_escolha"."""
    elif data.question_type == "certo_errado":
        type_instruction = """Todas as questões devem ser do tipo CERTO ou ERRADO (estilo CESPE/CEBRASPE).
O campo "options" deve ser ["Certo", "Errado"].
O campo "correct_answer" deve ser "Certo" ou "Errado".
O campo "type" deve ser "certo_errado"."""
    else:
        type_instruction = """Misture questões de múltipla escolha (5 alternativas A-E) e certo/errado.
Para múltipla escolha: options com 5 alternativas, correct_answer = letra (A-E), type = "multipla_escolha".
Para certo/errado: options = ["Certo", "Errado"], correct_answer = "Certo" ou "Errado", type = "certo_errado"."""

    difficulty_instruction = ""
    if data.difficulty == "facil":
        difficulty_instruction = "Nível FÁCIL: questões básicas e conceituais."
    elif data.difficulty == "medio":
        difficulty_instruction = "Nível MÉDIO: questões intermediárias que exigem compreensão aprofundada."
    elif data.difficulty == "dificil":
        difficulty_instruction = "Nível DIFÍCIL: questões complexas, com pegadinhas e que exigem raciocínio avançado."
    else:
        difficulty_instruction = "Misture questões de diferentes níveis de dificuldade (fácil, médio e difícil)."

    banca_info = f"Banca: {data.banca}. Siga o ESTILO e formato típico desta banca." if data.banca else "Sem banca específica."
    disciplina_info = f"Disciplina: {data.disciplina}." if data.disciplina else ""
    if data.topic: disciplina_info += f"\nRestrinja todas as questões ao assunto selecionado: {data.topic}."
    concurso_info = f"Concurso: {data.concurso}." if data.concurso else ""

    system_msg = f"""Você é um especialista em elaboração de questões para concursos públicos brasileiros.
Gere questões ORIGINAIS, realistas e de alta qualidade, no estilo de provas reais.

CONTEXTO:
{banca_info}
{disciplina_info}
{concurso_info}
{difficulty_instruction}

{type_instruction}

REGRAS:
- Gere exatamente {num_q} questões
- As questões devem ser originais mas no estilo de questões reais de concursos
- Cada questão deve ter enunciado claro e completo
- As alternativas devem ser plausíveis (não deve ser óbvio qual é a correta)
- A explicação deve ser detalhada e educativa
- Identifique a subdisciplina/tópico de cada questão
- Questões devem cobrir diferentes tópicos dentro da disciplina
- Para questões de interpretação de texto, inclua um "texto_base" (trecho, fragmento, artigo de lei, etc.) que o candidato deve ler para responder
- Pelo menos 20-30% das questões devem ter texto_base quando a disciplina envolver interpretação, legislação ou jurisprudência
- Se a questão não precisar de texto base, use null no campo texto_base

Responda APENAS com JSON válido no formato:
{{
  "questions": [
    {{
      "question_number": 1,
      "texto_base": "Texto de apoio/trecho para leitura, se aplicável. Null se não houver.",
      "question_text": "Texto completo da questão",
      "options": ["A) texto", "B) texto", "C) texto", "D) texto", "E) texto"],
      "correct_answer": "A",
      "explanation": "Explicação detalhada da resposta correta",
      "disciplina": "{data.disciplina or 'Geral'}",
      "subdisciplina": "Tópico específico",
      "difficulty": "medio",
      "type": "multipla_escolha"
    }}
  ]
}}"""

    prompt = f"Gere {num_q} questões de simulado para concurso público com as seguintes especificações:\n"
    if data.banca:
        prompt += f"- Banca: {data.banca}\n"
    if data.disciplina:
        prompt += f"- Disciplina: {data.disciplina}\n"
    if data.concurso:
        prompt += f"- Concurso: {data.concurso}\n"
    prompt += f"- Tipo: {data.question_type}\n- Dificuldade: {data.difficulty}\n"
    prompt += "\nRetorne APENAS o JSON com as questões."

    try:
        response = await request_gemini(task='study_question_generation', contents=prompt, config=dict(system_instruction=system_msg), user_id=user.user_id)

        json_str = response.text.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        parsed = json.loads(json_str.strip())
        questions = parsed.get("questions", [])

        if not questions:
            raise HTTPException(status_code=500, detail="A IA não conseguiu gerar as questões. Tente novamente.")
        if len(questions) != num_q or any(not isinstance(q, dict) or not q.get('question_text') or not q.get('correct_answer') for q in questions):
            raise HTTPException(502, 'A geração retornou quantidade ou questões inválidas. Nenhum simulado foi salvo; tente novamente.')
        for question in questions:
            question['provenance'] = 'inferred'
            if data.notebook_id:
                question['notebook_id'] = data.notebook_id
                question['disciplina'] = data.disciplina
            if data.topic_key is not None:
                question['topic_key'] = data.topic_key
                question['subdisciplina'] = data.topic

        simulado_id = f"sim_{uuid.uuid4().hex[:12]}"
        simulado_doc = {
            "simulado_id": simulado_id,
            "user_id": user.user_id,
            "title": data.title,
            "description": data.description or f"Simulado gerado por IA - {data.banca or ''} {data.disciplina or ''} {data.concurso or ''}".strip(),
            "source_type": "ai_generated",
            "banca": data.banca,
            "disciplina": data.disciplina,
            "concurso": data.concurso,
            "question_type": data.question_type,
            "difficulty": data.difficulty,
            "questions": questions,
            "questions_count": len(questions),
            "area_id": data.area_id,
            "program_id": data.program_id,
            "status": "ready",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        simulado_doc['notebook_id']=data.notebook_id
        return await catalog.create(user.user_id,request.headers.get('Idempotency-Key'),
            ['generate-simulado',data.model_dump()],simulado_doc,questions,xp=5)

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse generated simulado JSON: {e}")
        raise HTTPException(status_code=500, detail="Erro ao gerar simulado. Tente novamente.")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Simulado generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar simulado: {str(e)}")
