from fastapi import FastAPI, APIRouter, HTTPException, File, UploadFile, Form, Cookie, Response, Request, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure, CollectionInvalid
import hashlib
import os
import logging
import json
from pathlib import Path
from services import edital_analyses as sql_edital
from edital_quality import edital_context, needs_disciplines, generic_discipline, normalized_name, mark_discipline_quality
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Literal
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import aiofiles
import base64
from pypdf import PdfReader
import io

import random
import asyncio
import requests
import httpx
import secrets

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

GOOGLE_GEMINI_API_KEY = os.environ.get('GOOGLE_GEMINI_API_KEY', '')


FREETTS_URL = os.environ.get('FREETTS_URL', 'https://api.freetts.org')
FREE_TTS_VOICE = os.environ.get('FREE_TTS_VOICE', 'pt-BR-FranciscaNeural')

EIDOS_URL = os.environ.get('EIDOS_URL', 'https://eidosspeech.xyz/api/v1/tts')
EIDOS_API_KEY = os.environ.get('EIDOS_API_KEY', '')

def extract_pdf_text(content: bytes) -> str:
    """Extract text from a PDF using pypdf (memory-safe)."""
    try:
        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        for page_number, page in enumerate(reader.pages, 1):
            extracted = page.extract_text()
            if extracted:
                text_parts.append(f"[PÁGINA {page_number}]\n{extracted}")
        return "\n".join(text_parts)
    except Exception as e:
        logging.warning(f"Failed to extract PDF text: {e}")
        return ""


# ==================== FUZZY DEDUP DE CARGOS ====================

def _normalize_cargo_name(name: str) -> str:
    """Normalize typography only; role qualifiers are part of its identity."""
    import unicodedata, re as _re
    value = unicodedata.normalize("NFD", name or "").encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(_re.sub(r"[^a-z0-9\s]", " ", value).split())


def dedup_cargos_fuzzy(cargos: List[dict], threshold: float = 0.90) -> List[dict]:
    """Union only identical role identities. Threshold retained for call compatibility.

    Similarity is not evidence that two official positions are interchangeable.
    Missing versus explicit qualifiers are deliberately kept separate.
    """
    if not cargos:
        return cargos
    out: List[dict] = []
    norms: List[str] = []
    merges: List[tuple[str, str]] = []
    for c in cargos:
        cname = (c.get("nome") or "").strip()
        cnorm = _normalize_cargo_name(cname)
        if not cnorm:
            out.append(c); norms.append(cnorm); continue
        matched_idx = -1
        for i, existing in enumerate(norms):
            if not existing:
                continue
            identity_fields = ("codigo", "codigo_cargo", "especialidade", "area", "nivel")
            same_identity = all(_normalize_cargo_name(str(out[i].get(key) or "")) == _normalize_cargo_name(str(c.get(key) or "")) for key in identity_fields)
            if existing == cnorm and same_identity:
                matched_idx = i; break
        if matched_idx == -1:
            out.append(c); norms.append(cnorm)
        else:
            # merge disciplinas by name
            base = out[matched_idx]
            base_disc_names = {(d.get("nome") or "").strip().lower() for d in (base.get("disciplinas") or [])}
            for d in (c.get("disciplinas") or []):
                nm = (d.get("nome") or "").strip().lower()
                if nm and nm not in base_disc_names:
                    base.setdefault("disciplinas", []).append(d)
                    base_disc_names.add(nm)
            merges.append((cname, base.get("nome") or ""))
    if merges:
        logging.info(f"dedup_cargos_fuzzy merged {len(merges)} cargo(s): {merges}")
    return out


def _try_repair_json(s: str) -> Optional[dict]:
    """Best-effort recovery of a truncated JSON emitted by Gemini's Structured Output.

    Strategy:
      1) Try `json.loads` on the raw string (fast path, no-op if already valid).
      2) If truncated mid-array (e.g. ...`"conteudo_programatico":[{"assunto":"...` cut off),
         locate the last complete top-level "cargos" entry by scanning matching braces, then
         close the array + object.
      3) Return the parsed dict or None on total failure.
    Only attempts to recover the shape emitted by `analyze_edital_cargos` (has top-level
    `cargos` array). Safe: never raises.
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Encontra a lista de cargos e trunca no último `}` bem-formado
    cargos_start = s.find('"cargos"')
    if cargos_start < 0:
        return None
    bracket_start = s.find('[', cargos_start)
    if bracket_start < 0:
        return None

    # Faz scan char a char para achar o último `}` no nível de item do array
    depth_brace = 0
    depth_bracket = 1   # já entramos no [
    in_string = False
    escape = False
    last_valid_close = -1
    for i in range(bracket_start + 1, len(s)):
        ch = s[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth_brace += 1
        elif ch == '}':
            depth_brace -= 1
            if depth_brace == 0 and depth_bracket == 1:
                last_valid_close = i  # cargo completo terminou aqui
        elif ch == '[':
            depth_bracket += 1
        elif ch == ']':
            depth_bracket -= 1
            if depth_bracket == 0:
                # array fechou naturalmente — provavelmente já era válido, mas caiu aqui
                break

    if last_valid_close < 0:
        return None

    # Reconstrói: prefixo + fecha array + fecha objeto raiz
    repaired = s[: last_valid_close + 1] + "]}"
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


# ==================== GEMINI USAGE TRACKING ====================
# Rate limits documented by Google (free tier, subject to change):
GEMINI_FREE_TIER_RPD = {}  # Provider limits vary by account; never present guesses as quotas.

def _today_str_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

async def track_gemini_usage(user_id: str, model: str, delta: int = 1, usage=None, feature="text") -> None:
    from services.ai_usage import record_gemini
    await record_gemini(user_id, model, delta, usage, feature)

async def get_gemini_usage_today(user_id: str) -> dict:
    from services.ai_usage import gemini_today
    return await gemini_today(user_id)


async def get_user_api_key(user_id: str) -> Optional[str]:
    from ai.credentials import Credentials
    return (await Credentials().get(user_id)).get('gemini')

async def get_freellm_api_key(user_id: str) -> Optional[str]:
    return None

# ========== LLM CALLS ==========

async def call_llm(prompt: str, session_id: str = "default", system_message: str = "Você é um assistente útil.", user_id: Optional[str] = None, timeout_override: Optional[int] = None, task: str = 'assistant_chat') -> str:
    from ai.types import AIError
    if not user_id:
        return '⚠️ Faça login para usar IA.'
    keys = await agent_runtime.credentials.get(user_id)
    try:
        result = await agent_runtime.router.generate(task=task, keys=keys, user_id=user_id, prompt=prompt, system=system_message, timeout=timeout_override or 90, max_tokens=8192)
        await track_gemini_usage(user_id, result.model, usage=result.usage, feature=task)
        return result.text
    except AIError as error:
        if not keys: return '⚠️ Configure uma chave de IA nas configurações do assistente.'
        if error.kind in ('quota', 'rate_limit'): return '⚠️ Limite de IA atingido. Aguarde antes de tentar novamente.'
        return '⚠️ IA temporariamente indisponível. Seus dados foram preservados.'


def gemini_inline_part(data, mime_type):
    return {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(data).decode('ascii')}}


def gemini_file_part(file_uri, mime_type):
    return {"fileData": {"mimeType": mime_type, "fileUri": file_uri}}


async def upload_gemini_path(path, user_id):
    from gemini_service import upload_to_gemini as upload
    from types import SimpleNamespace
    import mimetypes
    key = await get_user_api_key(user_id)
    if not key:
        raise HTTPException(400, 'Configure sua chave Gemini no perfil.')
    if Path(path).stat().st_size > 25 * 1024 * 1024:
        raise HTTPException(413, 'Arquivo excede 25 MB.')
    content = await asyncio.to_thread(Path(path).read_bytes)
    uri = await upload(content, key, mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
    if not uri:
        raise HTTPException(502, 'Não foi possível processar o arquivo na IA.')
    return SimpleNamespace(uri=uri)


async def request_gemini(*, contents, config, user_id, task='document_analysis'):
    from gemini_service import call_gemini as generate
    from types import SimpleNamespace
    keys = await agent_runtime.credentials.get(user_id)
    key = keys.get('gemini')
    if not keys:
        raise HTTPException(400, 'Configure uma chave de IA nas configurações do assistente.')
    config = dict(config or {})
    system = config.pop('system_instruction', '')
    schema = config.pop('response_schema', None)
    fields = {'response_mime_type': 'responseMimeType', 'max_output_tokens': 'maxOutputTokens',
              'temperature': 'temperature', 'top_p': 'topP', 'top_k': 'topK'}
    options = {fields[k]: v for k, v in config.items() if k in fields}
    parts = [{'text': item} if isinstance(item, str) else item for item in (contents if isinstance(contents, list) else [contents])]
    text, error = await generate('', system, key, user_id=user_id, response_schema=schema,
                                 usage_callback=track_gemini_usage, parts=parts, config_options=options, task=task, keys=keys)
    if not text:
        raise HTTPException(429 if error == 'quota' else 502, 'A IA não respondeu. Confira sua chave e tente novamente.')
    return SimpleNamespace(text=text)

async def call_gemini(prompt: str, system_message: str, api_key: str, timeout_override: Optional[int] = None, user_id: Optional[str] = None, response_schema: Optional[dict] = None, task='edital_extract') -> tuple[Optional[str], Optional[str]]:
    from gemini_service import call_gemini as generate
    return await generate(prompt, system_message, api_key, timeout_override, user_id, response_schema, usage_callback=track_gemini_usage, task=task, keys=await agent_runtime.credentials.get(user_id) if user_id else None)

async def upload_to_gemini(pdf_content: bytes, api_key: str) -> Optional[str]:
    from gemini_service import upload_to_gemini as generate
    return await generate(pdf_content, api_key)

async def call_gemini_with_pdf(pdf_content: bytes, prompt_text: str, system_message: str, api_key: str, timeout: int = 120, response_schema: Optional[dict] = None, user_id: Optional[str] = None, inline_max_bytes: int = 15 * 1024 * 1024) -> tuple[Optional[str], Optional[str]]:
    from gemini_service import call_gemini_with_pdf as generate
    return await generate(pdf_content, prompt_text, system_message, api_key, timeout, response_schema, user_id, inline_max_bytes, usage_callback=track_gemini_usage, keys=await agent_runtime.credentials.get(user_id) if user_id else None)


app = FastAPI()
api_router = APIRouter(prefix="/api")

# ========== FREE TTS ==========

@api_router.post('/tts')
async def text_to_speech(request: Request, data: dict, session_token: Optional[str] = Cookie(None)):
    user = await get_current_user(authorization=request.headers.get('Authorization'), session_token=session_token)
    from ai.types import AIError
    if not agent_runtime.settings.voice: raise HTTPException(503, 'Voz desabilitada.')
    text = str(data.get('text', '')).strip()[:1000]
    if not text: raise HTTPException(422, 'Texto vazio.')
    try:
        result = await agent_runtime.router.generate(task='text_to_speech', keys=await agent_runtime.credentials.get(user.user_id), user_id=user.user_id, prompt=text)
        raw = base64.b64decode(result.data['data'])
        import wave
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000); wav.writeframes(raw)
        return {'audio_data': base64.b64encode(output.getvalue()).decode(), 'format': 'wav'}
    except AIError:
        return {'unavailable': True, 'fallback': 'browser_speech'}

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    timezone: str = 'America/Sao_Paulo'
    picture: Optional[str] = None
    xp: int = 0
    rank: str = "Recruta"
    birth_date: Optional[str] = None
    bio: Optional[str] = None
    gemini_api_key: Optional[str] = Field(default=None, exclude=True)
    has_gemini_key: bool = False
    gemini_key_last4: Optional[str] = None
    has_groq_key: bool = False
    groq_key_last4: Optional[str] = None
    created_at: datetime

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    gemini_api_key: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class SessionData(BaseModel):
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime

class Task(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    completed: bool = False
    date: str
    priority: str = "medium"
    xp_reward: int = 10
    recurrence: str = "once"  # once, daily, weekly, monthly
    is_template: bool = True
    created_at: datetime

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    date: str
    priority: Literal['low', 'medium', 'high'] = "medium"
    recurrence: Literal['once', 'daily', 'weekly', 'monthly'] = "once"

class Habit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    habit_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    color: str
    streak: int = 0
    best_streak: int = 0
    completions: List[str] = []
    created_at: datetime

class HabitCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#007AFF"

class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transaction_id: str
    user_id: str
    type: str
    amount: float
    category: str
    description: Optional[str] = None
    date: str
    created_at: datetime

class TransactionCreate(BaseModel):
    type: Literal['income', 'expense']
    amount: float = Field(gt=0, le=1000000000, allow_inf_nan=False)
    category: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    date: str

class Budget(BaseModel):
    model_config = ConfigDict(extra="ignore")
    budget_id: str
    user_id: str
    category: str
    limit: float
    spent: float = 0
    month: str
    created_at: datetime

class BudgetCreate(BaseModel):
    category: str
    limit: float
    month: str

class Goal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    goal_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    target_date: str
    progress: float = 0
    sprint_duration: int = 60
    daily_checks: List[str] = []
    sprints: List[Dict[str, Any]] = []
    created_at: datetime

class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target_date: str
    sprint_duration: int = 60

class Challenge(BaseModel):
    model_config = ConfigDict(extra="ignore")
    challenge_id: str
    title: str
    description: str
    xp_reward: int
    week_start: str
    week_end: str
    completed_by: List[str] = []
    created_at: datetime

class Achievement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    achievement_id: str
    user_id: str
    title: str
    description: str
    icon: str
    unlocked_at: datetime

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: str
    user_id: str
    role: str
    content: str
    transaction_data: Optional[Dict[str, Any]] = None
    created_at: datetime

class Report(BaseModel):
    model_config = ConfigDict(extra="ignore")
    report_id: str
    user_id: str
    type: str
    period: str
    data: Dict[str, Any]
    insights: str
    created_at: datetime

# ========== WORKOUT MODELS ==========
class WorkoutPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    plan_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    exercises: List[Dict[str, Any]] = []  # [{name, sets, reps, weight, notes, tutorial, video_url, muscle_group, rest_seconds}]
    plan_duration: str = "dia"  # dia, semana, mes, ciclo
    generated_by_ai: bool = False
    days: Optional[List[Dict[str, Any]]] = None  # For multi-day plans: [{day_name, day_label, exercises}]
    objective: Optional[str] = None
    level: Optional[str] = None
    created_at: datetime

class WorkoutPlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    exercises: List[Dict[str, Any]] = []
    plan_duration: str = "dia"
    days: Optional[List[Dict[str, Any]]] = None

from services.workout_generation_routes import WorkoutPlanGenerate

class WorkoutSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str
    user_id: str
    plan_id: str
    plan_name: str
    status: str = "active"  # active, completed, abandoned
    started_at: str
    completed_at: Optional[str] = None
    total_duration_seconds: int = 0
    exercises: List[Dict[str, Any]] = []  # [{name, sets, reps, weight, completed, time_spent_seconds, sets_completed}]
    current_exercise_idx: int = 0
    rest_timer_seconds: int = 60
    feedback: Optional[Dict[str, Any]] = None  # {difficulty: 1-5, feeling: str, notes: str}
    day_index: Optional[int] = None  # For multi-day plans

class WorkoutLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    log_id: str
    user_id: str
    plan_id: Optional[str] = None
    activity_type: str  # running, weightlifting, cycling, swimming, etc.
    name: str
    duration_minutes: int = 0
    distance_km: Optional[float] = None
    calories: Optional[int] = None
    exercises_completed: List[Dict[str, Any]] = []
    notes: Optional[str] = None
    xp_earned: int = 20
    completed: bool = True
    date: str
    created_at: datetime

class WorkoutLogCreate(BaseModel):
    plan_id: Optional[str] = None
    activity_type: str
    name: str
    duration_minutes: int = 0
    distance_km: Optional[float] = None
    calories: Optional[int] = None
    exercises_completed: List[Dict[str, Any]] = []
    notes: Optional[str] = None
    date: str

# ========== NOTIFICATION MODELS ==========
class Notification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    notification_id: str
    user_id: str
    title: str
    message: str
    type: str  # reminder, achievement, alert, system
    category: str  # workout, habit, task, hydration, custom
    scheduled_time: Optional[str] = None
    repeat: str = "none"  # none, daily, weekly, custom
    repeat_days: List[str] = []  # ["monday", "tuesday", etc.]
    enabled: bool = True
    channels: List[str] = ["in_app"]  # in_app, browser, email, whatsapp, telegram
    last_sent: Optional[str] = None
    created_at: datetime

class NotificationCreate(BaseModel):
    title: str
    message: str
    type: str = "reminder"
    category: str = "custom"
    scheduled_time: Optional[str] = None
    repeat: str = "none"
    repeat_days: List[str] = []
    channels: List[str] = ["in_app"]

class NotificationLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    log_id: str
    notification_id: str
    user_id: str
    sent_at: datetime
    channel: str
    status: str  # sent, read, dismissed

# ========== BODY MEASUREMENT MODELS ==========
class BodyMeasurement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    measurement_id: str
    user_id: str
    date: str
    # Peso e composição corporal
    weight_kg: Optional[float] = None
    body_fat_percentage: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    bone_mass_kg: Optional[float] = None
    water_percentage: Optional[float] = None
    visceral_fat: Optional[int] = None
    metabolic_age: Optional[int] = None
    bmr_kcal: Optional[int] = None  # Taxa metabólica basal
    # Medidas corporais (cm)
    height_cm: Optional[float] = None
    neck_cm: Optional[float] = None
    shoulders_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    abdomen_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    left_arm_cm: Optional[float] = None
    right_arm_cm: Optional[float] = None
    left_forearm_cm: Optional[float] = None
    right_forearm_cm: Optional[float] = None
    left_thigh_cm: Optional[float] = None
    right_thigh_cm: Optional[float] = None
    left_calf_cm: Optional[float] = None
    right_calf_cm: Optional[float] = None
    # Calculados
    bmi: Optional[float] = None  # IMC
    # Notas e observações
    notes: Optional[str] = None
    source: str = "manual"  # manual, pdf_import, bioimpedance
    created_at: datetime

class BodyMeasurementCreate(BaseModel):
    date: str
    weight_kg: Optional[float] = None
    body_fat_percentage: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    bone_mass_kg: Optional[float] = None
    water_percentage: Optional[float] = None
    visceral_fat: Optional[int] = None
    metabolic_age: Optional[int] = None
    bmr_kcal: Optional[int] = None
    height_cm: Optional[float] = None
    neck_cm: Optional[float] = None
    shoulders_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    abdomen_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    left_arm_cm: Optional[float] = None
    right_arm_cm: Optional[float] = None
    left_forearm_cm: Optional[float] = None
    right_forearm_cm: Optional[float] = None
    left_thigh_cm: Optional[float] = None
    right_thigh_cm: Optional[float] = None
    left_calf_cm: Optional[float] = None
    right_calf_cm: Optional[float] = None
    notes: Optional[str] = None
    source: str = "manual"

# ========== DAILY WORKOUT TRACKING ==========
class DailyWorkoutStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status_id: str
    user_id: str
    plan_id: str
    date: str
    exercises_status: Dict[int, bool] = {}  # {exercise_index: completed}
    completed: bool = False
    created_at: datetime
    updated_at: datetime

async def get_current_user(authorization: Optional[str] = None, session_token: Optional[str] = None) -> User:
    from services.auth import AuthService
    profile = await AuthService().current_user(authorization=authorization, session_token=session_token)
    return User(**profile)

@api_router.get("/")
async def root():
    return {"message": "Sirius API - Discipline is Destiny"}

# Only the four collections currently used by the mobile data service are syncable.
# Account/session/configuration collections must never be exposed through this API.
SYNC_TABLES = {
    "tasks": ("task_id", Task),
    "habits": ("habit_id", Habit),
    "transactions": ("transaction_id", Transaction),
    "goals": ("goal_id", Goal),
}

class SyncPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    operation: Literal["INSERT", "UPDATE", "DELETE"]
    data: Dict[str, Any]
    timestamp: str


def get_sync_config(table_name: str):
    config = SYNC_TABLES.get(table_name)
    if config is None:
        raise HTTPException(status_code=403, detail="Collection is not available for sync")
    return config


@api_router.post("/sync/{table_name}")
async def sync_table(
    table_name: str,
    payload: SyncPayload,
    request: Request,
    session_token: Optional[str] = Cookie(None)
):
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    id_field, record_model = get_sync_config(table_name)
    data = dict(payload.data)
    if data.get("user_id", user.user_id) != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if data.get(id_field, payload.record_id) != payload.record_id:
        raise HTTPException(status_code=422, detail="Record identifier does not match")
    allowed_fields = set(record_model.model_fields) | {"updated_at", "synced_at"}
    if set(data) - allowed_fields:
        raise HTTPException(status_code=422, detail="Unsupported sync fields")

    collection = db[table_name]
    selector = {id_field: payload.record_id, "user_id": user.user_id}
    if payload.operation == "DELETE":
        await collection.delete_one(selector)
        return {"success": True}

    existing = await collection.find_one(selector, {"_id": 0})
    if existing is None:
        if payload.operation == "UPDATE":
            raise HTTPException(status_code=404, detail="Record not found")
        # Avoid reusing another account's identifier, even though all writes are scoped.
        if await collection.find_one({id_field: payload.record_id}, {"_id": 0, id_field: 1}):
            raise HTTPException(status_code=409, detail="Record identifier is unavailable")

    now = datetime.now(timezone.utc).isoformat()
    merged = {**(existing or {}), **data, id_field: payload.record_id, "user_id": user.user_id}
    merged["created_at"] = (existing or {}).get("created_at", data.get("created_at") or now)
    # SQLite stores these values as JSON text; MongoDB consumers expect arrays.
    for field in ("completions", "daily_checks", "sprints"):
        if isinstance(merged.get(field), str):
            try:
                merged[field] = json.loads(merged[field])
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="Invalid sync list")
    if table_name == "tasks":
        merged["xp_reward"] = (existing or {}).get("xp_reward", 10)
    try:
        validated = record_model.model_validate(merged).model_dump(mode="json")
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid sync record")
    validated["updated_at"] = now
    validated["synced_at"] = now
    await collection.update_one(selector, {"$set": validated}, upsert=payload.operation == "INSERT")
    return {"success": True}


@api_router.get("/sync/{table_name}/{user_id}")
async def get_sync_data(
    table_name: str,
    user_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(None)
):
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    _, record_model = get_sync_config(table_name)
    if user.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    # Positive projection also keeps unexpected legacy/private fields out of responses.
    projection = {field: 1 for field in record_model.model_fields}
    projection.update({"updated_at": 1, "synced_at": 1, "_id": 0})
    return await db[table_name].find({"user_id": user.user_id}, projection).to_list(1000)










@api_router.post("/auth/test-gemini-key")
async def test_gemini_key(request: Request, data: Optional[dict] = None, session_token: Optional[str] = Cookie(None)):
    """Quickly validate a Gemini API key against Google (does NOT save).

    If `data.api_key` is passed, tests that key; otherwise tests the key already saved for the user.
    Returns diagnostic info so the profile page can show quota/status.
    """
    from urllib.parse import quote

    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    api_key = (data or {}).get("api_key") if data else None
    if not api_key:
        api_key = await get_user_api_key(user.user_id)
    if not api_key:
        return {
            "valid": False,
            "status": "missing",
            "message": "Nenhuma chave Gemini configurada.",
        }

    from ai.providers.gemini import GeminiProvider, BASE
    from ai.types import AIError
    try:
        await GeminiProvider().request('get', BASE + '/models', headers={'x-goog-api-key': api_key}, timeout=15)
        return {'valid': True, 'status': 'ok', 'message': 'Chave aceita pelo provedor. A disponibilidade e a quota de cada modelo podem variar.', 'usage_today': await get_gemini_usage_today(user.user_id)}
    except AIError as error:
        return {'valid': False, 'status': error.kind, 'message': 'Não foi possível validar a chave agora.'}




async def setup_activity_collections():
    # All activity/XP writers locate the locked user by user_id. A collection
    # scan under mixed transactional/non-transactional contention is avoidable.
    try:
        await db.users.create_index('user_id')
    except OperationFailure as exc:
        if exc.code not in (85, 86): raise  # Keep an existing equivalent unique index.
    # Creating namespaces inside concurrent transactions can conflict or block.
    # Prepare them before serving requests; multiple workers may start together.
    for name in ("ai_events", "task_instances", "activity_requests", "focus_sessions", "study_streaks", "study_dated_plans", "study_topic_reviews", "question_logs", "edital_jobs", "workout_sessions", "workout_logs", "study_targets", "study_attempts", "study_areas", "study_programs", "simulados", "simulado_attempts"):
        try:
            await db.create_collection(name)
        except CollectionInvalid:
            pass
        except OperationFailure as exc:
            if exc.code != 48:  # NamespaceExists from another starting worker.
                raise


def validate_activity_date(value: str) -> str:
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError
        parsed = datetime.strptime(value, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != value:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=422, detail="Date must be a valid YYYY-MM-DD")
    return value































@api_router.get("/chat/messages")
async def get_chat_messages(request: Request, session_token: Optional[str] = Cookie(None)):
    user = await get_current_user(authorization=request.headers.get('Authorization'), session_token=session_token)
    from services.conversations import Conversations
    return (await Conversations().read(user.user_id))['messages']

class ChatMessageCreate(BaseModel):
    content: str

@api_router.post("/chat/send")
async def send_chat_message(request: Request, message_data: ChatMessageCreate, session_token: Optional[str] = Cookie(None)):
    body = AiChatRequest(message=message_data.content.strip(), request_id=request.headers.get('Idempotency-Key') or uuid.uuid4().hex, page='/chat')
    return await ai_chat(request, body, session_token)

@api_router.post("/chat/analyze-image")
async def analyze_image_for_expenses(
    request: Request, 
    image: UploadFile = File(...),
    description: str = Form(""),
    session_token: Optional[str] = Cookie(None)
):
    await get_current_user(authorization=request.headers.get('Authorization'), session_token=session_token)
    raise HTTPException(410, 'Use /api/ai/attachments e /api/ai/chat para analisar a imagem e confirmar cada despesa antes de registrar.')











def calculate_rank(xp: int) -> str:
    ranks = [
        (0, "Recruta"),
        (200, "Soldado"),
        (500, "Cabo"),
        (1000, "Sargento"),
        (1800, "Subtenente"),
        (3000, "Tenente"),
        (4500, "Capitão"),
        (6500, "Major"),
        (9000, "Tenente-Coronel"),
        (12000, "Coronel"),
        (16000, "General de Brigada"),
        (21000, "General de Divisão"),
        (27000, "General de Exército"),
        (35000, "Marechal")
    ]
    for threshold, rank in reversed(ranks):
        if xp >= threshold:
            return rank
    return "Recruta"


def calculate_streak(completions: List[str]) -> int:
    if not completions:
        return 0
    
    today = datetime.now(timezone.utc).date()
    completions_dates = [datetime.fromisoformat(d).date() for d in completions]
    completions_dates.sort(reverse=True)
    
    if completions_dates[0] != today and completions_dates[0] != today - timedelta(days=1):
        return 0
    
    streak = 1
    for i in range(len(completions_dates) - 1):
        if completions_dates[i] - completions_dates[i+1] == timedelta(days=1):
            streak += 1
        else:
            break
    return streak

def calculate_best_streak(completions: List[str]) -> int:
    """Calculate the longest streak ever from all completions"""
    if not completions:
        return 0
    
    completions_dates = sorted([datetime.fromisoformat(d).date() for d in completions])
    
    if len(completions_dates) == 1:
        return 1
    
    best_streak = 1
    current_streak = 1
    
    for i in range(1, len(completions_dates)):
        if completions_dates[i] - completions_dates[i-1] == timedelta(days=1):
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            current_streak = 1
    
    return best_streak

# ========== FINANCE CATEGORIES ==========
DEFAULT_FINANCE_CATEGORIES = ["alimentação", "transporte", "moradia", "saúde", "educação", "lazer", "investimentos", "salário", "freelance", "outros"]














class CreditCard(BaseModel):
    model_config = ConfigDict(extra="ignore")
    card_id: str
    user_id: str
    name: str
    limit: float
    closing_day: int
    due_day: int
    created_at: datetime

class CreditCardCreate(BaseModel):
    name: str
    limit: float
    closing_day: int
    due_day: int

class Invoice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invoice_id: str
    card_id: str
    user_id: str
    month: str
    amount: float
    paid: bool = False
    created_at: datetime

class Projection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    projection_id: str
    user_id: str
    month: str
    description: str
    amount: float
    category: str
    projection_type: str  # "fixed", "installment", "manual"
    is_fixed: bool = False  # Despesa fixa que se repete todo mês
    repeat_count: Optional[int] = None  # Número de vezes que se repete (se não for fixa)
    remaining_repeats: Optional[int] = None  # Repetições restantes
    source_transaction_id: Optional[str] = None  # ID da transação original (para parcelas)
    installment_number: Optional[int] = None  # Número da parcela atual
    total_installments: Optional[int] = None  # Total de parcelas
    card_id: Optional[str] = None  # Cartão associado (se aplicável)
    created_at: datetime

class ProjectionCreate(BaseModel):
    description: str
    amount: float
    category: str
    month: str
    is_fixed: bool = False
    repeat_count: Optional[int] = None

class CardChargeRequest(BaseModel):
    amount: float
    description: str
    category: str
    payment_type: str = "vista"  # "vista" ou "parcelado"
    installments: Optional[int] = 1  # Número de parcelas
    start_month: str = "current"  # "current" ou "next" - quando começa a primeira parcela






# ========== PROJECTION ENDPOINTS ==========







# ========== WORKOUT ENDPOINTS ==========















# ========== AI WORKOUT GENERATION ==========



# ========== IMPROVE WORKOUT (MELHORAR TREINO) ==========



# ========== WORKOUT SESSION ENDPOINTS ==========












@api_router.post("/workouts/calculate-warmup")
async def calculate_warmup(request: Request, session_token: Optional[str] = Cookie(None)):
    """Calculate warmup sets based on working weight."""
    auth_header = request.headers.get("Authorization")
    await get_current_user(authorization=auth_header, session_token=session_token)
    
    body = await request.json()
    working_weight = body.get("weight", 0)
    if not working_weight or working_weight <= 0:
        return {"warmup_sets": []}
    
    warmup_percentages = [0.5, 0.6, 0.7, 0.8]
    warmup_reps = [8, 6, 4, 2]
    
    warmup_sets = []
    for i, (pct, reps) in enumerate(zip(warmup_percentages, warmup_reps)):
        w = round(working_weight * pct, 1)
        if w > 0:
            warmup_sets.append({
                "set_number": i + 1,
                "percentage": f"{int(pct * 100)}%",
                "weight": w,
                "reps": reps,
                "label": f"{int(pct * 100)}% x {reps}" if w < working_weight else "Trabalho"
            })
    
    warmup_sets.append({
        "set_number": len(warmup_sets) + 1,
        "percentage": "100%",
        "weight": working_weight,
        "reps": "Trabalho",
        "label": "Trabalho"
    })
    
    return {"warmup_sets": warmup_sets}






# ========== NOTIFICATION ENDPOINTS ==========
@api_router.get("/notifications")
async def get_notifications(request: Request, session_token: Optional[str] = Cookie(None)):
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    notifications = await db.notifications.find({"user_id": user.user_id}, {"_id": 0}).to_list(100)
    for notif in notifications:
        if isinstance(notif['created_at'], str):
            notif['created_at'] = datetime.fromisoformat(notif['created_at'])
    return notifications

@api_router.post("/notifications")
async def create_notification(request: Request, notif_data: NotificationCreate, session_token: Optional[str] = Cookie(None)):
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    notification_id = f"notif_{uuid.uuid4().hex[:12]}"
    notification_doc = {
        "notification_id": notification_id,
        "user_id": user.user_id,
        "title": notif_data.title,
        "message": notif_data.message,
        "type": notif_data.type,
        "category": notif_data.category,
        "scheduled_time": notif_data.scheduled_time,
        "repeat": notif_data.repeat,
        "repeat_days": notif_data.repeat_days,
        "enabled": True,
        "channels": notif_data.channels,
        "last_sent": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notification_doc)
    notification_doc.pop('_id', None)  # Remove MongoDB ObjectId
    notification_doc['created_at'] = datetime.fromisoformat(notification_doc['created_at'])
    return Notification(**notification_doc)

@api_router.patch("/notifications/{notification_id}")
async def update_notification(request: Request, notification_id: str, notif_data: NotificationCreate, session_token: Optional[str] = Cookie(None)):
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    update_data = {
        "title": notif_data.title,
        "message": notif_data.message,
        "type": notif_data.type,
        "category": notif_data.category,
        "scheduled_time": notif_data.scheduled_time,
        "repeat": notif_data.repeat,
        "repeat_days": notif_data.repeat_days,
        "channels": notif_data.channels
    }
    
    result = await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user.user_id},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification updated"}

@api_router.patch("/notifications/{notification_id}/toggle")
async def toggle_notification(request: Request, notification_id: str, session_token: Optional[str] = Cookie(None)):
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    notif = await db.notifications.find_one({"notification_id": notification_id, "user_id": user.user_id}, {"_id": 0})
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    new_enabled = not notif['enabled']
    await db.notifications.update_one(
        {"notification_id": notification_id},
        {"$set": {"enabled": new_enabled}}
    )
    return {"message": "Notification toggled", "enabled": new_enabled}

@api_router.delete("/notifications/{notification_id}")
async def delete_notification(request: Request, notification_id: str, session_token: Optional[str] = Cookie(None)):
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    result = await db.notifications.delete_one({"notification_id": notification_id, "user_id": user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification deleted"}

@api_router.get("/notifications/pending")
async def get_pending_notifications(request: Request, session_token: Optional[str] = Cookie(None)):
    """Get notifications that should be triggered now"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    current_time = datetime.now(timezone.utc).strftime("%H:%M")
    current_day = datetime.now(timezone.utc).strftime("%A").lower()
    
    # Find enabled notifications for current time
    notifications = await db.notifications.find({
        "user_id": user.user_id,
        "enabled": True,
        "scheduled_time": current_time
    }, {"_id": 0}).to_list(100)
    
    pending = []
    for notif in notifications:
        should_send = False
        if notif['repeat'] == "none":
            should_send = True
        elif notif['repeat'] == "daily":
            should_send = True
        elif notif['repeat'] == "weekly":
            if current_day in [d.lower() for d in notif.get('repeat_days', [])]:
                should_send = True
        elif notif['repeat'] == "custom":
            if current_day in [d.lower() for d in notif.get('repeat_days', [])]:
                should_send = True
        
        if should_send:
            pending.append(notif)
    
    return pending

@api_router.post("/notifications/{notification_id}/send")
async def mark_notification_sent(request: Request, notification_id: str, channel: str, session_token: Optional[str] = Cookie(None)):
    """Mark a notification as sent and log it"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    # Update last_sent timestamp
    await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user.user_id},
        {"$set": {"last_sent": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Log the notification send
    log_id = f"nlog_{uuid.uuid4().hex[:12]}"
    log_doc = {
        "log_id": log_id,
        "notification_id": notification_id,
        "user_id": user.user_id,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "status": "sent"
    }
    await db.notification_logs.insert_one(log_doc)
    
    return {"message": "Notification marked as sent", "log_id": log_id}

# ========== NOTIFICATION TEMPLATES ==========
@api_router.get("/notification-templates")
async def get_notification_templates():
    """Get predefined notification templates"""
    templates = [
        {
            "id": "hydration",
            "title": "💧 Hora de Beber Água",
            "message": "Lembre-se de se manter hidratado! Beba um copo de água.",
            "category": "hydration",
            "suggested_times": ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"],
            "repeat": "daily"
        },
        {
            "id": "workout",
            "title": "💪 Hora do Treino",
            "message": "Não esqueça do seu treino de hoje! Bora mover o corpo!",
            "category": "workout",
            "suggested_times": ["06:00", "07:00", "18:00", "19:00"],
            "repeat": "custom"
        },
        {
            "id": "morning_tasks",
            "title": "📋 Revisão Matinal",
            "message": "Bom dia! Hora de revisar suas tarefas do dia.",
            "category": "task",
            "suggested_times": ["07:00", "08:00"],
            "repeat": "daily"
        },
        {
            "id": "evening_review",
            "title": "🌙 Revisão Noturna",
            "message": "Como foi seu dia? Hora de revisar o progresso e planejar amanhã.",
            "category": "task",
            "suggested_times": ["21:00", "22:00"],
            "repeat": "daily"
        },
        {
            "id": "habit_check",
            "title": "✅ Verificar Hábitos",
            "message": "Já completou seus hábitos de hoje?",
            "category": "habit",
            "suggested_times": ["20:00"],
            "repeat": "daily"
        },
        {
            "id": "stretch",
            "title": "🧘 Hora de Alongar",
            "message": "Faça uma pausa e alongue-se por 5 minutos.",
            "category": "workout",
            "suggested_times": ["10:00", "15:00"],
            "repeat": "daily"
        },
        {
            "id": "posture",
            "title": "🪑 Verificar Postura",
            "message": "Corrija sua postura! Costas retas, ombros relaxados.",
            "category": "custom",
            "suggested_times": ["09:00", "11:00", "14:00", "16:00"],
            "repeat": "daily"
        }
    ]
    return templates

# ========== BODY MEASUREMENTS ENDPOINTS ==========





# ========== PDF ANALYSIS ENDPOINT ==========

# ========== AI RECOMMENDATIONS ==========

# ========== MOTIVATIONAL QUOTES ==========

# ========== DAILY WORKOUT STATUS ==========




# ========== NUTRITION MODELS ==========
class Meal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    meal_id: str
    user_id: str
    name: str
    meal_type: str  # breakfast, lunch, dinner, snack
    foods: List[Dict[str, Any]] = []  # [{name, calories, protein, carbs, fat, quantity, unit}]
    total_calories: int = 0
    total_protein: float = 0
    total_carbs: float = 0
    total_fat: float = 0
    date: str
    notes: Optional[str] = None
    created_at: datetime

class MealCreate(BaseModel):
    name: str
    meal_type: str
    foods: List[Dict[str, Any]] = []
    date: str
    notes: Optional[str] = None

class NutritionGoal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    goal_id: str
    user_id: str
    daily_calories: int = 2000
    daily_protein: float = 150
    daily_carbs: float = 250
    daily_fat: float = 65
    water_goal_ml: int = 2000
    created_at: datetime
    updated_at: datetime

class NutritionGoalCreate(BaseModel):
    daily_calories: int = 2000
    daily_protein: float = 150
    daily_carbs: float = 250
    daily_fat: float = 65
    water_goal_ml: int = 2000

class WaterLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    log_id: str
    user_id: str
    amount_ml: int
    date: str
    created_at: datetime

class Diet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    diet_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    diet_type: str  # cutting, bulking, maintenance, keto, low_carb, etc.
    meals_plan: List[Dict[str, Any]] = []  # [{meal_type, suggested_foods, target_calories}]
    active: bool = True
    start_date: str
    end_date: Optional[str] = None
    created_at: datetime

class DietCreate(BaseModel):
    name: str
    description: Optional[str] = None
    diet_type: str
    meals_plan: List[Dict[str, Any]] = []
    start_date: str
    end_date: Optional[str] = None

class Recipe(BaseModel):
    model_config = ConfigDict(extra="ignore")
    recipe_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    ingredients: List[Dict[str, Any]] = []  # [{name, quantity, unit}]
    instructions: List[str] = []
    prep_time_minutes: int = 0
    cook_time_minutes: int = 0
    servings: int = 1
    calories_per_serving: int = 0
    protein_per_serving: float = 0
    carbs_per_serving: float = 0
    fat_per_serving: float = 0
    tags: List[str] = []  # healthy, quick, high-protein, etc.
    ai_generated: bool = False
    created_at: datetime

# ========== STUDY MODELS ==========
class StudyArea(BaseModel):
    model_config = ConfigDict(extra="ignore")
    area_id: str
    user_id: str
    name: str  # Faculdade, Concursos, Trabalho, Outros
    description: Optional[str] = None
    color: str = "#007AFF"
    icon: str = "book"
    order: int = 0
    created_at: datetime

class StudyAreaCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#007AFF"
    icon: str = "book"

class StudyProgram(BaseModel):
    model_config = ConfigDict(extra="ignore")
    program_id: str
    user_id: str
    area_id: str
    name: str  # Ex: "Curso de Direito", "Concurso TRF5"
    description: Optional[str] = None
    color: str = "#007AFF"
    icon: str = "book"
    target_date: Optional[str] = None  # Meta date (exam date, graduation, etc.)
    status: str = "active"  # active, completed, paused
    total_questions: int = 0
    correct_questions: int = 0
    created_at: datetime

class StudyProgramCreate(BaseModel):
    area_id: str
    name: str
    description: Optional[str] = None
    color: str = "#007AFF"
    icon: str = "book"
    target_date: Optional[str] = None

class Notebook(BaseModel):
    model_config = ConfigDict(extra="ignore")
    notebook_id: str
    user_id: str
    area_id: str
    program_id: Optional[str] = None  # Optional link to a program
    name: str  # Matéria/Assunto
    description: Optional[str] = None
    color: str = "#007AFF"
    tags: List[str] = []
    total_study_time_minutes: int = 0
    total_questions: int = 0
    correct_questions: int = 0
    created_at: datetime

class NotebookCreate(BaseModel):
    area_id: str
    program_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    color: str = "#007AFF"
    tags: List[str] = []

class QuestionLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    log_id: str
    user_id: str
    notebook_id: str
    program_id: Optional[str] = None
    total: int = 0
    correct: int = 0
    incorrect: int = 0
    source: str = "manual"  # manual, quiz, ai
    date: str
    created_at: datetime

class QuestionLogCreate(BaseModel):
    notebook_id: str
    total: int
    correct: int
    source: str = "manual"

class FocusSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    focus_id: str
    user_id: str
    notebook_id: Optional[str] = None
    focus_minutes: int = 25
    break_minutes: int = 5
    completed: bool = False
    date: str
    notes: Optional[str] = None
    xp_earned: int = 0
    created_at: datetime

class FocusSessionCreate(BaseModel):
    notebook_id: Optional[str] = None
    focus_minutes: int = Field(default=25, ge=1, le=120)
    break_minutes: int = Field(default=5, ge=1, le=30)
    notes: Optional[str] = Field(default=None, max_length=110000)

class StudyNote(BaseModel):
    model_config = ConfigDict(extra="ignore")
    note_id: str
    user_id: str
    notebook_id: str
    title: str
    content: str
    tags: List[str] = []
    links: List[Dict[str, str]] = []  # [{title, url}]
    attachments: List[Dict[str, Any]] = []  # [{name, type, url/data}]
    created_at: datetime
    updated_at: datetime

class StudyNoteCreate(BaseModel):
    notebook_id: str
    title: str
    content: str
    tags: List[str] = []
    links: List[Dict[str, str]] = []

class StudyTask(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_id: str
    user_id: str
    notebook_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    task_type: str  # reading, exercise, review, project, exam
    recurrence: str = "once"  # once, daily, weekly, monthly
    deadline: Optional[str] = None
    reminder: Optional[str] = None
    completed: bool = False
    completed_at: Optional[str] = None
    last_completed_date: Optional[str] = None  # For recurring tasks
    priority: str = "medium"
    estimated_minutes: int = 30
    actual_minutes: int = 0
    notes: Optional[str] = None
    xp_reward: int = 20
    created_at: datetime

class StudyTaskCreate(BaseModel):
    notebook_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    task_type: str = "reading"
    recurrence: str = "once"  # once, daily, weekly, monthly
    deadline: Optional[str] = None
    reminder: Optional[str] = None
    priority: str = "medium"
    estimated_minutes: int = 30

class StudySession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str
    user_id: str
    notebook_id: str
    duration_minutes: int
    date: str
    notes: Optional[str] = None
    xp_earned: int = 0
    created_at: datetime

class StudySessionCreate(BaseModel):
    notebook_id: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(gt=0, le=720, strict=True)
    date: str
    notes: Optional[str] = Field(default=None, max_length=2000)

class StudySchedule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schedule_id: str
    user_id: str
    notebook_id: str
    day_of_week: str  # monday, tuesday, etc.
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    repeat: bool = True
    created_at: datetime

class StudyScheduleCreate(BaseModel):
    notebook_id: str
    day_of_week: str
    start_time: str
    end_time: str
    repeat: bool = True

class Flashcard(BaseModel):
    model_config = ConfigDict(extra="ignore")
    flashcard_id: str
    user_id: str
    notebook_id: str
    deck_name: str
    front: str  # Question
    back: str  # Answer
    tags: List[str] = []
    # Spaced Repetition Fields
    ease_factor: float = 2.5
    interval_days: int = 1
    repetitions: int = 0
    next_review: str  # Date
    last_review: Optional[str] = None
    created_at: datetime

class FlashcardCreate(BaseModel):
    notebook_id: str
    deck_name: str
    front: str
    back: str
    tags: List[str] = []

class FlashcardReview(BaseModel):
    quality: int  # 0-5 (0=forgot, 5=perfect)

class Quiz(BaseModel):
    model_config = ConfigDict(extra="ignore")
    quiz_id: str
    user_id: str
    notebook_id: str
    title: str
    questions: List[Dict[str, Any]] = []  # [{question, options, correct_answer, explanation}]
    ai_generated: bool = False
    created_at: datetime

class QuizCreate(BaseModel):
    notebook_id: str
    title: str
    questions: List[Dict[str, Any]] = []

class QuizAttempt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    attempt_id: str
    user_id: str
    quiz_id: str
    score: float
    answers: List[Dict[str, Any]] = []  # [{question_idx, selected_answer, correct}]
    completed_at: datetime

# ========== SIMULADO MODELS ==========





class StudyStreak(BaseModel):
    model_config = ConfigDict(extra="ignore")
    streak_id: str
    user_id: str
    current_streak: int = 0
    best_streak: int = 0
    last_study_date: Optional[str] = None
    total_study_days: int = 0
    created_at: datetime

class StudyStats(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stats_id: str
    user_id: str
    notebook_id: str
    total_time_minutes: int = 0
    sessions_count: int = 0
    flashcards_reviewed: int = 0
    quizzes_completed: int = 0
    average_quiz_score: float = 0
    tasks_completed: int = 0

# ========== NUTRITION ENDPOINTS ==========




@api_router.post("/nutrition/estimate-food")
async def estimate_food_nutrition(request: Request, session_token: Optional[str] = Cookie(None)):
    """Use AI to estimate nutritional values for a food item"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    body = await request.json()
    food_name = body.get("food_name", "").strip()
    quantity = body.get("quantity", "").strip()
    
    if not food_name:
        raise HTTPException(status_code=400, detail="Nome do alimento é obrigatório")
    if not quantity:
        raise HTTPException(status_code=400, detail="Quantidade/peso é obrigatório")
    
    prompt = f"""Analise o seguinte alimento e estime os valores nutricionais com precisão.

Alimento: {food_name}
Quantidade/Peso: {quantity}

Retorne APENAS um JSON válido (sem markdown, sem explicação) com esta estrutura exata:
{{
  "food_name": "nome do alimento formatado",
  "quantity": "{quantity}",
  "calories": número inteiro (kcal),
  "protein": número decimal (gramas),
  "carbs": número decimal (gramas),
  "fat": número decimal (gramas),
  "fiber": número decimal (gramas),
  "sodium": número decimal (mg),
  "sugar": número decimal (gramas)
}}

Use valores baseados em tabelas nutricionais brasileiras (TACO) quando possível.
Considere a quantidade informada para calcular os valores proporcionais.
Se for um prato composto (ex: "prato feito"), estime os ingredientes típicos.
Retorne SOMENTE o JSON, nada mais."""

    system_msg = "Você é um nutricionista especialista em tabelas nutricionais brasileiras. Retorne apenas JSON válido sem markdown."
    
    try:
        response = await call_llm(prompt, f"food_estimate_{user.user_id}_{uuid.uuid4().hex[:6]}", system_msg, user_id=user.user_id, task='nutrition_generation')
        
        # Parse JSON from response
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[1] if "\n" in json_str else json_str[3:]
            json_str = json_str.rsplit("```", 1)[0]
        json_str = json_str.strip()
        
        nutrition_data = json.loads(json_str)
        
        return {
            "success": True,
            "food_name": nutrition_data.get("food_name", food_name),
            "quantity": nutrition_data.get("quantity", quantity),
            "calories": int(nutrition_data.get("calories", 0)),
            "protein": round(float(nutrition_data.get("protein", 0)), 1),
            "carbs": round(float(nutrition_data.get("carbs", 0)), 1),
            "fat": round(float(nutrition_data.get("fat", 0)), 1),
            "fiber": round(float(nutrition_data.get("fiber", 0)), 1),
            "sodium": round(float(nutrition_data.get("sodium", 0)), 1),
            "sugar": round(float(nutrition_data.get("sugar", 0)), 1)
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Não foi possível estimar os nutrientes. Tente novamente ou insira manualmente.",
            "food_name": food_name,
            "quantity": quantity,
            "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 0, "sugar": 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro ao estimar nutrientes: {str(e)}",
            "food_name": food_name,
            "quantity": quantity,
            "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 0, "sugar": 0
        }


@api_router.post("/nutrition/estimate-foods-batch")
async def estimate_foods_batch(request: Request, session_token: Optional[str] = Cookie(None)):
    """Use AI to estimate nutritional values for multiple food items at once"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    body = await request.json()
    foods = body.get("foods", [])
    
    if not foods or len(foods) == 0:
        raise HTTPException(status_code=400, detail="Lista de alimentos é obrigatória")
    
    if len(foods) > 20:
        raise HTTPException(status_code=400, detail="Máximo de 20 alimentos por vez")
    
    # Build the food list for the prompt
    food_list_text = ""
    for i, food in enumerate(foods):
        name = food.get("food_name", "").strip()
        qty = food.get("quantity", "").strip()
        if name and qty:
            food_list_text += f"{i+1}. {name} - {qty}\n"
    
    if not food_list_text:
        raise HTTPException(status_code=400, detail="Nenhum alimento válido na lista")
    
    prompt = f"""Analise os seguintes alimentos e estime os valores nutricionais de CADA UM com precisão.

ALIMENTOS:
{food_list_text}

Retorne APENAS um JSON válido (sem markdown, sem explicação) com esta estrutura exata:
{{
  "foods": [
    {{
      "index": 0,
      "food_name": "nome do alimento formatado",
      "quantity": "quantidade informada",
      "calories": número inteiro (kcal),
      "protein": número decimal (gramas),
      "carbs": número decimal (gramas),
      "fat": número decimal (gramas),
      "fiber": número decimal (gramas),
      "sodium": número decimal (mg),
      "sugar": número decimal (gramas)
    }}
  ]
}}

Use valores baseados em tabelas nutricionais brasileiras (TACO) quando possível.
Considere a quantidade informada para calcular os valores proporcionais.
Se for um prato composto (ex: "prato feito"), estime os ingredientes típicos.
Retorne UM item para CADA alimento listado, na mesma ordem.
Retorne SOMENTE o JSON, nada mais."""

    system_msg = "Você é um nutricionista especialista em tabelas nutricionais brasileiras. Retorne apenas JSON válido sem markdown."
    
    try:
        response = await call_llm(prompt, f"food_batch_{user.user_id}_{uuid.uuid4().hex[:6]}", system_msg, user_id=user.user_id, task='assistant_chat')
        
        # Parse JSON from response
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[1] if "\n" in json_str else json_str[3:]
            json_str = json_str.rsplit("```", 1)[0]
        json_str = json_str.strip()
        
        result = json.loads(json_str)
        estimated_foods = result.get("foods", [])
        
        # Normalize the response
        normalized = []
        for i, food in enumerate(foods):
            # Find matching estimation (by index or position)
            est = next((e for e in estimated_foods if e.get("index") == i), None)
            if not est and i < len(estimated_foods):
                est = estimated_foods[i]
            
            if est:
                normalized.append({
                    "index": i,
                    "success": True,
                    "food_name": est.get("food_name", food.get("food_name", "")),
                    "quantity": est.get("quantity", food.get("quantity", "")),
                    "calories": int(est.get("calories", 0)),
                    "protein": round(float(est.get("protein", 0)), 1),
                    "carbs": round(float(est.get("carbs", 0)), 1),
                    "fat": round(float(est.get("fat", 0)), 1),
                    "fiber": round(float(est.get("fiber", 0)), 1),
                    "sodium": round(float(est.get("sodium", 0)), 1),
                    "sugar": round(float(est.get("sugar", 0)), 1)
                })
            else:
                normalized.append({
                    "index": i,
                    "success": False,
                    "food_name": food.get("food_name", ""),
                    "quantity": food.get("quantity", ""),
                    "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 0, "sugar": 0
                })
        
        return {
            "success": True,
            "foods": normalized
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Não foi possível estimar os nutrientes. Tente novamente.",
            "foods": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro ao estimar nutrientes: {str(e)}",
            "foods": []
        }















# ========== IMPORT MEAL PLAN ==========


# ========== STUDY ENDPOINTS ==========




# ========== STUDY PROGRAMS ==========





# ========== IMPORT EDITAL - AI STUDY PROGRAM GENERATOR ==========













# ========== QUESTION TRACKING ==========



# ========== FOCUS/POMODORO ==========



# ========== AI STUDY ASSISTANT ==========

@api_router.post("/study/ai-chat")
async def study_ai_chat(request: Request, data: dict, session_token: Optional[str] = Cookie(None)):
    """Compatibility alias; all conversational work belongs to Sirius Agent."""
    user = await get_current_user(authorization=request.headers.get('Authorization'), session_token=session_token)
    body = AiChatRequest(message=data.get('message', ''), conversation_id=data.get('conversation_id', 'primary'),
                         request_id=data.get('request_id') or uuid.uuid4().hex, page='/studies',
                         page_context=json.dumps({'notebook_id': data.get('notebook_id')}))
    result = await agent_runtime.chat(user.user_id, body)
    return {**result, 'response': result['ai_message']['content']}




































# ========== PDF CONTENT ANALYSIS ENDPOINT ==========



# ========== SIMULADOS ENDPOINTS ==========

















# ========== ANALYZE EDITAL (MULTI-CARGO) ==========

_DISCIPLINA_SCHEMA = {
    "type": "object",
    "properties": {
        "nome": {"type": "string"},
        "peso": {"type": "number"},
            "peso_fonte": {"type": "string"},
            "num_questoes_fonte": {"type": "string"},
        "num_questoes": {"type": "integer"},
        "grupo": {"type": "string"},
        "topicos": {"type": "array", "items": {"type": "string"}},
        "conteudo_programatico": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "assunto": {"type": "string"},
                    "subtopicos": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["assunto"],
            },
        },
    },
    "required": ["nome"],
}


def _strip_json_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```json"):
        s = s[7:]
    if s.startswith("```"):
        s = s[3:]
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()


def _parse_json_lenient(s: str) -> Optional[dict]:
    s = _strip_json_fences(s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return _try_repair_json(s)


def _normalize_disciplinas(discs) -> List[dict]:
    """Coage disciplinas ao formato esperado (respostas sem responseSchema variam de shape)."""
    out: List[dict] = []
    for d in discs or []:
        if isinstance(d, str):
            d = {"nome": d}
        if not isinstance(d, dict) or not d.get("nome"):
            continue
        top = d.get("topicos")
        if isinstance(top, str):
            d["topicos"] = [t.strip() for t in top.replace(";", "\n").splitlines() if t.strip()]
        cp = d.get("conteudo_programatico")
        if isinstance(cp, str):
            d["conteudo_programatico"] = [{"assunto": cp.strip(), "subtopicos": []}] if cp.strip() else []
        elif isinstance(cp, list):
            d["conteudo_programatico"] = [
                {"assunto": x, "subtopicos": []} if isinstance(x, str) else x
                for x in cp if isinstance(x, (str, dict))
            ]
        for f, default in (("peso", 1), ("num_questoes", 0)):
            v = d.get(f)
            if not isinstance(v, int):
                try:
                    d[f] = float(v) if f == "peso" else int(float(v))
                except (TypeError, ValueError):
                    d[f] = default
        out.append(d)
    return out


def _fill_cp_from_topicos(cargos_list: List[dict]) -> List[dict]:
    """Se o modelo deixou conteudo_programatico vazio mas preencheu topicos, sintetiza o CP a partir deles."""
    for c in cargos_list:
        for d in (c.get("disciplinas") or []):
            if not d.get("conteudo_programatico") and d.get("topicos"):
                d["conteudo_programatico"] = [{"assunto": t, "subtopicos": []} for t in d["topicos"] if t]
    return cargos_list



def _merge_hydrated_disciplinas(cargos_list: List[dict], parsed: dict) -> int:
    """Repair incomplete cargos without borrowing another role's specific subjects."""
    comuns = _normalize_disciplinas(parsed.get("disciplinas_comuns") or [])
    por_cargo = {normalized_name(c.get("nome")): c.get("disciplinas") or []
                 for c in parsed.get("cargos") or [] if isinstance(c, dict)}
    hydrated = 0
    for cargo in cargos_list:
        if not needs_disciplines(cargo):
            continue
        name = normalized_name(cargo.get("nome"))
        if not name or name not in por_cargo:
            continue
        candidates = comuns + _normalize_disciplinas(por_cargo[name])
        if not candidates or any(generic_discipline(d) for d in candidates):
            continue
        # Retain already extracted real subjects, replace group placeholders.
        previous = [d for d in _normalize_disciplinas(cargo.get("disciplinas")) if not generic_discipline(d)]
        merged = {normalized_name(d.get("nome")): d for d in previous}
        merged.update({normalized_name(d.get("nome")): d for d in candidates})
        proposal = {**cargo, "disciplinas": list(merged.values())}
        if not needs_disciplines(proposal):
            cargo["disciplinas"] = proposal["disciplinas"]
            hydrated += 1
    return hydrated


def _build_hydration_prompt(nomes: List[str]) -> str:
    lista = "\n".join(f"- {n}" for n in nomes)
    return f"""Você recebeu um edital de concurso público brasileiro.

Já sabemos que os cargos/perfis abaixo existem neste edital. Sua ÚNICA tarefa agora é extrair as DISCIPLINAS cobradas nas provas de cada um deles:

{lista}

REGRAS:
1) Se o edital tiver disciplinas COMUNS a todos os cargos (ex: "Conhecimentos Básicos", "Língua Portuguesa para todos os cargos"), coloque-as em "disciplinas_comuns" (com conteúdo programático COMPLETO) e NÃO as repita dentro de cada cargo.
2) Em "cargos", inclua APENAS as disciplinas ESPECÍFICAS de cada cargo (conhecimentos específicos). Se um cargo não tiver disciplinas específicas próprias, retorne "disciplinas": [] para ele.
3) Para cada disciplina preencha: "nome", "peso" (preserve decimais; 1 provisório se não informado), "num_questoes" (inteiro; 0 se não informado), "topicos" e "conteudo_programatico". Inclua peso_fonte e num_questoes_fonte como trechos literais do edital; use "" se não encontrados. Não replique totais de questões de grupos em cada disciplina.
4) "conteudo_programatico" é OBRIGATÓRIO e NUNCA pode ser vazio: copie FIELMENTE a lista oficial de assuntos/subtópicos daquela disciplina, exatamente como está na seção de conteúdo programático do edital (geralmente em "DOS CONTEÚDOS PROGRAMÁTICOS", "DO CONTEÚDO PROGRAMÁTICO", "DAS PROVAS" ou em ANEXO).
5) NUNCA retorne tudo vazio: todo edital tem conteúdo programático.
6) Se o edital agrupar várias matérias sob "Conhecimentos Específicos", liste CADA matéria como uma disciplina SEPARADA (ex: "Direito Constitucional", "Direito Administrativo"), nunca uma única disciplina genérica chamada "Conhecimentos Específicos".
7) Não invente nada que não esteja no edital. Português brasileiro em todos os campos."""


_HYDRATION_SYSTEM_MSG = (
    "Você é um extrator determinístico de conteúdo programático de editais de concursos públicos "
    "brasileiros. Sua prioridade absoluta é encontrar TODAS as disciplinas e seus conteúdos."
)

_HYDRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "disciplinas_comuns": {"type": "array", "items": _DISCIPLINA_SCHEMA},
        "cargos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "disciplinas": {"type": "array", "items": _DISCIPLINA_SCHEMA},
                },
                "required": ["nome"],
            },
        },
    },
    "required": ["disciplinas_comuns", "cargos"],
}


async def _hydrate_missing_disciplinas(pdf_text: str, cargos_list: List[dict], api_key: str, user_id: str, chunk_size: int = 2) -> int:
    """2º passo: extrai disciplinas dos cargos que vieram sem ou só com grupos genéricos."""
    missing = [c for c in cargos_list if needs_disciplines(c)]
    if not missing:
        return 0
    logging.info(f"analyze-edital: {len(missing)} cargo(s) sem disciplinas — iniciando hidratação (passo 2)")
    total_hydrated = 0
    for start in range(0, len(missing), chunk_size):
        chunk = missing[start:start + chunk_size]
        nomes = [c.get("nome", "") for c in chunk]
        text_clip = edital_context(pdf_text, nomes)
        for tentativa in range(2):
            prompt = _build_hydration_prompt(nomes) + f"\n\nTEXTO DO EDITAL:\n{text_clip}"
            result, err = await call_gemini(prompt, _HYDRATION_SYSTEM_MSG, api_key, timeout_override=180, user_id=user_id, response_schema=_HYDRATION_SCHEMA)
            parsed = _parse_json_lenient(result) if result else None
            if not parsed:
                logging.warning(f"analyze-edital: hidratação (lote {start//chunk_size + 1}, tentativa {tentativa+1}) falhou (err={err})")
                continue
            total_disc = len(parsed.get("disciplinas_comuns") or []) + sum(
                len(c.get("disciplinas") or []) for c in (parsed.get("cargos") or [])
            )
            if total_disc < 2 and tentativa == 0:
                logging.warning(f"analyze-edital: hidratação (lote {start//chunk_size + 1}) retornou só {total_disc} disciplina(s) — repetindo lote")
                continue
            total_hydrated += _merge_hydrated_disciplinas(chunk, parsed)
            if not any(needs_disciplines(c) for c in chunk):
                break
    logging.info(f"analyze-edital: hidratação preencheu disciplinas de {total_hydrated}/{len(missing)} cargo(s)")
    return total_hydrated


_CARGO_TEXT_FIELDS = ("vagas", "remuneracao", "escolaridade")


def _sanitize_cargos(cargos_list: List[dict]) -> List[dict]:
    """Trunca campos textuais degenerados (loops de repetição do modelo) e nomes gigantes."""
    for c in cargos_list:
        if isinstance(c.get("nome"), str) and len(c["nome"]) > 160:
            c["nome"] = c["nome"][:160].rstrip()
        if c.get("disciplinas"):
            c["disciplinas"] = _normalize_disciplinas(c["disciplinas"])
        for f in _CARGO_TEXT_FIELDS:
            v = c.get(f)
            if isinstance(v, str) and len(v) > 200:
                c[f] = v[:200].rstrip() + "…"
    return cargos_list


def _detect_min_cargos(pdf_text: str) -> int:
    """Detecta heuristicamente o nº mínimo de perfis numerados ("PERFIL: 1.", "PERFIL 2)"...) no edital."""
    import re as _re
    nums = {int(m.group(1)) for m in _re.finditer(r"(?i)PERFIL\s*[:\-–]?\s*(\d{1,2})\s*[\.\)]", pdf_text or "")}
    return len(nums) if len(nums) >= 2 else 0


_ENUM_CARGOS_SCHEMA = {
    "type": "object",
    "properties": {
        "cargos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "vagas": {"type": "string"},
                    "remuneracao": {"type": "string"},
                    "escolaridade": {"type": "string"},
                },
                "required": ["nome"],
            },
        },
    },
    "required": ["cargos"],
}


async def _enumerate_cargos_text(pdf_text: str, api_key: str, user_id: str, min_cargos: int, hint_block: str) -> List[dict]:
    """Retry focado: enumera SOMENTE os cargos/perfis (sem disciplinas) via texto extraído do PDF."""
    text_clip = pdf_text[:80_000]
    prompt = f"""Você recebeu o texto extraído de um edital de concurso público brasileiro.

TAREFA ÚNICA: liste TODOS os cargos / perfis / especialidades / áreas de atuação oferecidos, sem omitir nenhum. NÃO extraia disciplinas nem conteúdo programático agora.

REGRAS:
1) Cada perfil/especialidade numerado ou nomeado no edital é UM item independente em "cargos".
2) Foram detectados automaticamente PELO MENOS {min_cargos} perfis numerados no texto (ex: "PERFIL: 1.", "PERFIL: 2." ...). Seu array "cargos" DEVE ter no mínimo {min_cargos} itens.
3) "nome" = nome oficial completo (cargo + perfil). "vagas", "remuneracao", "escolaridade" = strings CURTAS (máx 1 linha cada); use "" se não houver.
4) Não invente cargos. Português brasileiro.
{hint_block}

Responda APENAS com JSON no formato exato:
{{"cargos":[{{"nome":"","vagas":"","remuneracao":"","escolaridade":""}}]}}

TEXTO DO EDITAL:
{text_clip}"""
    result, err = await call_gemini(
        prompt,
        "Você é um extrator determinístico de cargos e perfis de editais de concursos públicos brasileiros. Nunca omita um perfil.",
        api_key, timeout_override=180, user_id=user_id,
    )
    if not result:
        logging.warning(f"analyze-edital: enumeração de cargos (retry) falhou (err={err})")
        return []
    parsed = _parse_json_lenient(result)
    if not parsed:
        return []
    return parsed.get("cargos") or []


async def _hydrate_disciplinas_from_text(pdf_text: str, cargo_nome: str, api_key: str, user_id: str) -> List[dict]:
    """Fallback no import: extrai disciplinas de um cargo usando o texto do PDF armazenado na análise."""
    if not pdf_text or not pdf_text.strip():
        return []
    prompt = (
        _build_hydration_prompt([cargo_nome])
        + "\n\nResponda APENAS com JSON válido no formato: "
          '{"disciplinas_comuns": [...], "cargos": [{"nome": "...", "disciplinas": [...]}]}'
        + f"\n\nTRECHOS DO EDITAL PARA ESTE CARGO:\n{edital_context(pdf_text, [cargo_nome])}"
    )
    result, err = await call_gemini(prompt, _HYDRATION_SYSTEM_MSG, api_key, timeout_override=150, user_id=user_id, response_schema=_HYDRATION_SCHEMA)
    if not result:
        logging.warning(f"import-edital: hidratação por texto falhou (err={err})")
        return []
    parsed = _parse_json_lenient(result)
    if not parsed:
        logging.warning("import-edital: hidratação por texto retornou JSON inválido")
        return []
    fake_cargo = {"nome": cargo_nome, "disciplinas": []}
    _merge_hydrated_disciplinas([fake_cargo], parsed)
    return fake_cargo.get("disciplinas") or []


@api_router.post("/study/programs/analyze-edital")
async def analyze_edital_cargos(
    request: Request,
    file: UploadFile = File(...),
    force: bool = Query(False, description="Reanalisa o PDF completo, incluindo os anexos finais, sem reutilizar o cache"),
    session_token: Optional[str] = Cookie(None)
):
    """Analyze an edital PDF and return ALL available cargos/perfis before generating the program.

    Improvements vs previous version:
      - Uses Gemini Structured Output (responseSchema) → JSON válido garantido, sem markdown fences.
      - Prompt reforçado exigindo enumerar TODOS os cargos/perfis/especializações/áreas
        (mesmo quando compartilham conhecimentos básicos) para não sub-contar posições.
      - Pré-scan do texto do PDF para detectar heurísticas de cargos/perfis, injetadas no prompt.
      - Cache por hash SHA-256 do PDF → re-envios do mesmo edital retornam instantaneamente,
        preservando quota Gemini do usuário.
      - Pipeline em 2 passos para editais com muitos cargos: (1) enumera cargos + disciplinas
        genéricas, (2) hidrata conteúdo programático detalhado. Isso evita truncamento e
        garante que nenhum cargo seja "resumido".
    """
    import hashlib
    import re as _re

    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    return await process_edital_analysis(user, file, force)


async def process_edital_analysis(user, file, force=False):
    import hashlib
    import re as _re
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos")

    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Limite de 20MB.")

    user_api_key = await get_user_api_key(user.user_id)
    if not user_api_key:
        raise HTTPException(status_code=400, detail="Configure sua chave Gemini no perfil para usar este recurso.")

    # ---- Cache lookup by PDF hash ----
    pdf_hash = hashlib.sha256(content).hexdigest()
    cached = None
    if not force:
        cached = await sql_edital.cached(user.user_id, pdf_hash, 5)
    if (
        cached and cached.get("cargos")
        and all(not needs_disciplines(c) for c in cached["cargos"])
        and len(cached["cargos"]) >= _detect_min_cargos(cached.get("pdf_text", ""))
    ):
        # Refresh expiry and return cached (só usa cache se houver disciplinas e nº de cargos plausível)
        new_analysis_id = str(uuid.uuid4())
        cached_copy = {
            "analysis_id": new_analysis_id,
            "user_id": user.user_id,
            "pdf_hash": pdf_hash,
            "analysis_version": 5,
            "concurso": cached.get("concurso", {}),
            "multiple_cargos": cached.get("multiple_cargos", False),
            "cargos": cached.get("cargos", []),
            "pdf_filename": file.filename,
            "pdf_text": cached.get("pdf_text", ""),
            "pdf_pages": cached.get("pdf_pages", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            "from_cache": True,
        }
        await sql_edital.save(user.user_id,cached_copy)
        return {
            "success": True,
            "analysis_id": new_analysis_id,
            "concurso": cached_copy["concurso"],
            "multiple_cargos": cached_copy["multiple_cargos"],
            "cargos": cached_copy["cargos"],
            "cached": True,
            "message": f"Edital recuperado do cache. {len(cached_copy['cargos'])} cargo(s)/perfil(is).",
        }

    # ---- Pré-scan do PDF para dar dicas de cargos/perfis ao modelo ----
    pdf_text = (await asyncio.to_thread(extract_pdf_text, content)) or ""
    hints: List[str] = []
    if pdf_text:
        # Captura linhas contendo palavras-chave de cargo/perfil
        keywords = _re.compile(
            r"\b(cargo|perfil|especializa[cç][ãa]o|[áa]rea\s+de\s+atua[cç][ãa]o|" 
            r"vagas?\s*(reservadas|do\s+cargo)?)\b",
            _re.IGNORECASE,
        )
        seen = set()
        for line in pdf_text.splitlines():
            ln = line.strip()
            if 4 <= len(ln) <= 180 and keywords.search(ln):
                key = _re.sub(r"\s+", " ", ln.lower())
                if key not in seen:
                    seen.add(key)
                    hints.append(ln)
                if len(hints) >= 60:
                    break

    hint_block = ""
    if hints:
        hint_block = (
            "\n\nLINHAS SUSPEITAS DETECTADAS AUTOMATICAMENTE NO PDF (use-as APENAS como pistas "
            "para não deixar nenhum cargo/perfil de fora — não copie literalmente):\n"
            + "\n".join(f"- {h}" for h in hints[:60])
        )

    # Heurística: nº mínimo de perfis numerados detectados no texto (ex: "PERFIL: 1." ... "PERFIL: 12.")
    min_cargos_detectados = _detect_min_cargos(pdf_text)
    if min_cargos_detectados:
        hint_block += (
            f"\n\nATENÇÃO: o texto do edital contém PELO MENOS {min_cargos_detectados} perfis numerados "
            f"(padrão \"PERFIL: N.\"). O array \"cargos\" DEVE ter no mínimo {min_cargos_detectados} itens."
        )

    # ---- JSON Schema estrito (Gemini Structured Output) ----
    # Schema mínimo e robusto — Gemini valida antes de emitir.
    disciplina_schema = {
        "type": "object",
        "properties": {
            "nome": {"type": "string"},
            "peso": {"type": "number"},
            "peso_fonte": {"type": "string"},
            "num_questoes_fonte": {"type": "string"},
            "num_questoes": {"type": "integer"},
            "grupo": {"type": "string"},
            "topicos": {"type": "array", "items": {"type": "string"}},
            "conteudo_programatico": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "assunto": {"type": "string"},
                        "subtopicos": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["assunto"],
                },
            },
        },
        "required": ["nome", "grupo"],
    }
    cargo_schema = {
        "type": "object",
        "properties": {
            "nome": {"type": "string"},
            "vagas": {"type": "string"},
            "remuneracao": {"type": "string"},
            "escolaridade": {"type": "string"},
            "taxa_inscricao": {"type": "string"},
            "disciplinas": {"type": "array", "items": disciplina_schema},
        },
        "required": ["nome"],
    }
    response_schema = {
        "type": "object",
        "properties": {
            "concurso": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "orgao": {"type": "string"},
                    "banca": {"type": "string"},
                    "visao_geral": {"type": "string"},
                    "prazos": {"type": "array", "items": {
                        "type": "object", "properties": {
                            "label": {"type": "string"},
                            "data": {"type": "string"},
                            "fonte": {"type": "string"},
                        }, "required": ["label", "data", "fonte"],
                    }},
                },
            },
            "multiple_cargos": {"type": "boolean"},
            "cargos": {"type": "array", "items": cargo_schema},
        },
        "required": ["concurso", "multiple_cargos", "cargos"],
    }

    prompt_text = f"""Você recebeu o PDF completo de um edital de concurso público brasileiro.

TAREFA: Extrair TODOS os cargos / perfis / especializações / áreas de atuação oferecidos pelo edital, sem omitir nenhum.

No objeto concurso, inclua visao_geral (resumo breve) e prazos (inscrições, pagamento, isenção, provas e recursos) apenas quando expressos no documento. Cada prazo deve conter label com seu escopo/cargo quando específico, data como aparece no edital e fonte com o trecho literal completo que sustenta a data. Nunca estime datas. No cargo, inclua taxa_inscricao apenas se informada para aquele cargo. Ausências: string vazia ou lista vazia.

REGRAS OBRIGATÓRIAS (leia com atenção):
1) LISTAGEM COMPLETA — Se o edital tiver 13 perfis, o array "cargos" DEVE ter 13 itens. Nunca resuma, nunca agrupe, nunca abrevie.
2) Cada "perfil", "especialidade", "especialização", "área de atuação", "modalidade", "opção de vaga" ou "cargo" distinto listado no edital é UM item independente em "cargos". Se dois perfis compartilham o mesmo edital mas se inscrevem separadamente, são DOIS cargos.
3) "multiple_cargos" = true se `cargos.length > 1`, caso contrário false.
4) Para cada cargo, preencha:
   - "nome" = nome oficial do cargo/perfil/especialidade (como aparece no edital).
   - "vagas" = número de vagas (string, pode ser "CR" para cadastro reserva).
   - "remuneracao" = remuneração inicial (string). Se não houver, "".
   - "escolaridade" = requisito de escolaridade. Se não houver, "".
   - "disciplinas" = TODAS as disciplinas cobradas para ESSE cargo específico.
5) Para cada disciplina:
   - "nome" = NOME DA DISCIPLINA INDIVIDUAL (ex: "Língua Portuguesa", nunca "Conhecimentos Gerais")
   - "grupo" = nome do GRUPO/TÓPICO a que pertence (ex: "Grupo I - Conhecimentos Básicos", "Grupo II - Conhecimentos Específicos", "Conhecimentos Gerais", "Conhecimentos Específicos")
   - "peso" = peso da disciplina, preservando decimais. Se não houver, use 1 apenas para planejamento provisório.
   - "peso_fonte" e "num_questoes_fonte" = trecho literal da tabela/seção que sustenta cada valor, incluindo disciplina/grupo e número. Se ausente, use "".
   - Nunca atribua a cada disciplina o total de questões de um grupo ou prova. Use 0 quando não houver quantidade individualizada.
   - "num_questoes" = número de questões (inteiro). Se não houver, use 0.
   - "topicos" = resumo curto (até 10 itens).
   - "conteudo_programatico" = lista COMPLETA do conteúdo oficial.
6) Nunca invente cargos, disciplinas ou tópicos. Se algo não estiver no edital, use "" ou 0.
7) Português brasileiro em TODOS os campos.

8) REGRA CRÍTICA — NUNCA use nomes de grupos/genéricos como nome de disciplina.
   Exemplo CORRETO de como expandir grupos:
   Se o edital diz: "Grupo I - Conhecimentos Gerais: Língua Portuguesa, Raciocínio Lógico"
   Você DEVE retornar DUAS disciplinas: {{"nome": "Língua Portuguesa", "grupo": "Grupo I - Conhecimentos Gerais"}}
   e {{"nome": "Raciocínio Lógico", "grupo": "Grupo I - Conhecimentos Gerais"}}
   Você NUNCA deve retornar {{"nome": "Conhecimentos Gerais"}} — isso está ERRADO.

   Exemplo CORRETO de grupo com sub-tópicos numerados:
   Se o edital diz: "NOÇÕES DE DIREITO: 1 Direito Administrativo, 2 Agentes Públicos"
   Você DEVE retornar UMA disciplina: {{"nome": "Noções de Direito", "grupo": "Conhecimentos Específicos"}}
   com "conteudo_programatico": [{{"assunto": "Direito Administrativo"}}, {{"assunto": "Agentes Públicos"}}]
   NUNCA crie disciplinas separadas para cada item numerado — os números são sub-tópicos.

9) Se o edital define grupos COMUNS a todos os cargos (ex: "Conhecimentos Básicos para todos os cargos"), REPLIQUE essas disciplinas dentro de CADA cargo. É PROIBIDO retornar cargo com disciplinas vazias.
{hint_block}
"""

    system_msg = (
        "Você é um extrator determinístico de editais de concursos públicos brasileiros. "
        "Sua prioridade absoluta é NÃO PERDER NENHUM cargo, perfil, especialidade ou área de atuação. "
        "Prefira listar cargos duplicados a omitir um."
    )

    try:
        try:
            edital_context(pdf_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        full_prompt = f"{prompt_text}\n\nTEXTO COMPLETO DO EDITAL:\n{edital_context(pdf_text)}"
        result, error_type = await call_gemini(
            full_prompt, system_msg, user_api_key,
            timeout_override=180, user_id=user.user_id,
            response_schema=response_schema,
        )
        if not result:
            if error_type == "quota":
                raise HTTPException(status_code=500, detail="Sua cota da API Gemini esgotou. Tente amanhã ou crie outra chave em https://aistudio.google.com/apikey.")
            if error_type in ("invalid", "empty"):
                raise HTTPException(status_code=500, detail="Sua chave Gemini é inválida ou foi revogada. Gere uma nova em https://aistudio.google.com/apikey.")
            raise HTTPException(status_code=500, detail=f"Erro ao contactar API Gemini (tipo={error_type or 'unknown'}). Tente novamente.")

        json_str = result.strip()
        # Remove eventuais code fences caso o modelo ignore o responseMimeType
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        # (fallback robusto) Se o JSON estiver truncado, tenta:
        #   1) recuperar até o último cargo válido cortando após "]" final antes do último trailing
        #   2) se falhar, tenta json_repair (simple: fechar aspas/colchetes)
        json_str_clean = json_str.strip()
        try:
            parsed = json.loads(json_str_clean)
        except json.JSONDecodeError as jerr:
            logging.warning(f"analyze-edital: JSON inválido ({jerr}). Tentando reparo. Tamanho resposta: {len(json_str_clean)} chars.")
            parsed = _try_repair_json(json_str_clean)
            if parsed is None:
                # Logar preview para diagnóstico
                logging.error(f"analyze-edital: reparo JSON falhou. Head: {json_str_clean[:400]!r} ... Tail: {json_str_clean[-400:]!r}")
                raise HTTPException(
                    status_code=500,
                    detail="A IA devolveu JSON inválido/incompleto. Tente novamente — se persistir, envie um PDF menor ou apenas as páginas do conteúdo programático.",
                )
            logging.info(f"analyze-edital: JSON reparado com sucesso. Cargos recuperados: {len(parsed.get('cargos') or [])}")

        cargos_list = parsed.get("cargos") or []
        # (item 3) — dedup fuzzy para proteger contra o modelo emitir cargos duplicados
        # com grafias ligeiramente diferentes ("Analista TI - Redes" e "Analista de TI Redes").
        cargos_list = dedup_cargos_fuzzy(cargos_list, threshold=0.92)

        # Passo 1b: se o modelo enumerou MENOS cargos que os perfis numerados detectados no texto,
        # refaz a enumeração com uma chamada focada só em cargos (resposta curta = muito mais confiável).
        if min_cargos_detectados and len(cargos_list) < min_cargos_detectados:
            logging.warning(
                f"analyze-edital: modelo retornou {len(cargos_list)} cargo(s), mas heurística detectou "
                f">= {min_cargos_detectados} perfis. Re-enumerando cargos..."
            )
            enum_cargos = await _enumerate_cargos_text(pdf_text, user_api_key, user.user_id, min_cargos_detectados, hint_block)
            if enum_cargos:
                cargos_list = dedup_cargos_fuzzy(cargos_list + enum_cargos, threshold=0.92)
                logging.info(f"analyze-edital: após re-enumeração, {len(cargos_list)} cargo(s)")

        cargos_list = _sanitize_cargos(cargos_list)
        parsed["multiple_cargos"] = len(cargos_list) > 1

        # Passo 2 do pipeline: hidrata cargos cujas disciplinas estão vazias ou são apenas
        # grupos genéricos (ex: só "Conhecimentos Gerais" e "Conhecimentos Específicos").
        if cargos_list and any(needs_disciplines(c) for c in cargos_list):
            await _hydrate_missing_disciplinas(pdf_text, cargos_list, user_api_key, user.user_id)

        _fill_cp_from_topicos(cargos_list)
        mark_discipline_quality(cargos_list)
        from study_resources import scoring_evidence
        from study_resources import sourced_deadlines
        if isinstance(parsed.get("concurso"), dict):
            parsed["concurso"]["prazos"] = sourced_deadlines(parsed["concurso"].get("prazos"), pdf_text)
        from edital_sources import source_pages, locate_subject
        pages = source_pages(pdf_text)
        from edital_audit import audit_cargos
        audit_cargos(cargos_list, pages)
        from ai.edital_verifier import verify as verify_edital
        independent_verification = await verify_edital(agent_runtime.router, await agent_runtime.credentials.get(user.user_id), user.user_id, cargos_list, pages)
        for cargo in cargos_list:
            for discipline in cargo.get("disciplinas", []):
                discipline.update(scoring_evidence(discipline, pdf_text))
                discipline["fontes"] = locate_subject(discipline.get("nome"), pages)

        analysis_id = str(uuid.uuid4())
        # (item 6) — guardamos o texto extraído do PDF para alimentar o chat sobre este edital
        # sem precisar re-uploadar o PDF a cada mensagem (Gemini File URIs expiram em 48h).
        analysis_doc = {
            "analysis_id": analysis_id,
            "user_id": user.user_id,
            "pdf_hash": pdf_hash,
            "analysis_version": 5,
            "concurso": parsed.get("concurso", {}),
            "multiple_cargos": parsed["multiple_cargos"],
            "cargos": cargos_list,
            "pdf_filename": file.filename,
            "pdf_text": edital_context(pdf_text),
            "pdf_pages": pages,
            "independent_verification": independent_verification,
            "created_at": datetime.now(timezone.utc).isoformat(),
            # (item 4) — expiração longa para permitir comparação futura de editais
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            "from_cache": False,
        }
        await sql_edital.save(user.user_id,analysis_doc)
        if agent_runtime.settings.rag:
            await agent_runtime.retrieval.index_edital(user.user_id, analysis_id)
        await agent_runtime.automations.emit(user.user_id, 'edital.updated', analysis_id)

        return {
            "success": True,
            "analysis_id": analysis_id,
            "concurso": parsed.get("concurso", {}),
            "multiple_cargos": parsed["multiple_cargos"],
            "cargos": cargos_list,
            "cached": False,
            "independent_verification": independent_verification,
            "message": (
                f"Edital analisado! {len(cargos_list)} cargo(s)/perfil(is) identificado(s)."
            ),
        }

    except json.JSONDecodeError as e:
        logging.error(f"analyze-edital JSONDecodeError (não recuperável): {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar resposta da IA. Tente novamente.")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"analyze-edital exceção inesperada: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao analisar edital: {type(e).__name__}: {str(e)[:200]}")


# ========== EDITAIS: LIST / COMPARE / CHAT ==========
# (itens 4 e 6 do backlog)










@api_router.post("/study/programs/edital-chat")
async def edital_chat(request: Request, data: dict, session_token: Optional[str] = Cookie(None)):
    """Compatibility alias for the shared conversation and owner-checked RAG."""
    user = await get_current_user(authorization=request.headers.get('Authorization'), session_token=session_token)
    aid = data.get('analysis_id')
    await agent_runtime.retrieval.index_edital(user.user_id, aid)
    body = AiChatRequest(message=data.get('question', ''), conversation_id=data.get('conversation_id', 'primary'),
                         request_id=data.get('request_id') or uuid.uuid4().hex, page='/studies',
                         page_context=json.dumps({'analysis_id': aid}))
    result = await agent_runtime.chat(user.user_id, body)
    return {**result, 'answer': result['ai_message']['content']}




# ========== STUDY AI CHAT WITH FILE UPLOAD ==========

@api_router.post("/study/ai-chat-with-file")
async def study_ai_chat_with_file(
    request: Request,
    file: UploadFile = File(...),
    message: str = Form(""),
    context_type: str = Form("summarize"),
    notebook_id: Optional[str] = Form(None),
    session_token: Optional[str] = Cookie(None)
):
    """Removed parallel chat: attachments and messages now have separate operations."""
    await get_current_user(authorization=request.headers.get('Authorization'), session_token=session_token)
    raise HTTPException(410, 'Envie o arquivo em /api/ai/attachments e converse com Sirius em /api/ai/chat.')


# ========== MIND MAP GENERATION ==========







# ========== PROGRESS HISTORY / COMPARATOR ==========



# ========== SCHEDULE-BASED NOTIFICATIONS ==========

@api_router.post("/study/programs/{program_id}/create-reminders")
async def create_schedule_reminders(
    request: Request,
    program_id: str,
    data: dict,
    session_token: Optional[str] = Cookie(None)
):
    """Create notifications/reminders from schedule blocks"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    program = await db.study_programs.find_one({"program_id": program_id, "user_id": user.user_id}, {"_id": 0})
    if not program:
        raise HTTPException(status_code=404, detail="Programa não encontrado")
    
    schedules = await db.study_schedules.find(
        {"program_id": program_id, "user_id": user.user_id}, {"_id": 0}
    ).to_list(200)
    
    notebooks = await db.notebooks.find(
        {"program_id": program_id, "user_id": user.user_id}, {"_id": 0}
    ).to_list(100)
    nb_lookup = {nb["notebook_id"]: nb for nb in notebooks}
    
    reminder_minutes_before = data.get("minutes_before", 5)
    include_end_reminder = data.get("include_end_reminder", False)
    
    day_map_reverse = {
        "monday": "Seg", "tuesday": "Ter", "wednesday": "Qua",
        "thursday": "Qui", "friday": "Sex", "saturday": "Sáb", "sunday": "Dom"
    }
    
    created = 0
    for sched in schedules:
        nb = nb_lookup.get(sched.get("notebook_id"))
        disc_name = nb["name"] if nb else "Matéria"
        day_label = day_map_reverse.get(sched.get("day_of_week", ""), "")
        
        # Calculate reminder time (X minutes before start)
        start_time = sched.get("start_time", "08:00")
        try:
            parts = start_time.split(":")
            total_mins = int(parts[0]) * 60 + int(parts[1]) - reminder_minutes_before
            if total_mins < 0:
                total_mins = 0
            reminder_time = f"{total_mins // 60:02d}:{total_mins % 60:02d}"
        except (ValueError, IndexError):
            reminder_time = start_time
        
        # Map day_of_week to repeat_days
        day_of_week = sched.get("day_of_week", "")
        
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        notif_doc = {
            "notification_id": notification_id,
            "user_id": user.user_id,
            "title": f"Hora de estudar: {disc_name}",
            "message": f"{day_label} {start_time} - {sched.get('end_time', '')} | {sched.get('tipo_estudo', 'Estudo')}",
            "type": "reminder",
            "category": "study",
            "scheduled_time": reminder_time,
            "repeat": "weekly",
            "repeat_days": [day_of_week],
            "enabled": True,
            "channels": ["in_app", "browser"],
            "last_sent": None,
            "program_id": program_id,
            "schedule_id": sched.get("schedule_id"),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.notifications.insert_one(notif_doc)
        created += 1
    
    return {
        "success": True,
        "created": created,
        "message": f"{created} lembretes criados para o cronograma de estudos!"
    }


# ========== FIX: PENDING NOTIFICATIONS WITH TIMEZONE ==========

@api_router.get("/notifications/check")
async def check_notifications(request: Request, timezone_offset: int = 0, session_token: Optional[str] = Cookie(None)):
    """Check for pending notifications considering user timezone"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    # Use timezone offset from client to calculate local time
    utc_now = datetime.now(timezone.utc)
    user_local = utc_now - timedelta(minutes=timezone_offset)
    current_time = user_local.strftime("%H:%M")
    current_day = user_local.strftime("%A").lower()
    
    # Find enabled notifications matching current time (with 2 minute window)
    try:
        h, m = map(int, current_time.split(":"))
        time_start_mins = h * 60 + m - 1
        time_end_mins = h * 60 + m + 1
        
        times_to_check = []
        for t_mins in range(max(0, time_start_mins), min(1440, time_end_mins + 1)):
            times_to_check.append(f"{t_mins // 60:02d}:{t_mins % 60:02d}")
    except (ValueError, IndexError):
        times_to_check = [current_time]
    
    notifications = await db.notifications.find({
        "user_id": user.user_id,
        "enabled": True,
        "scheduled_time": {"$in": times_to_check}
    }, {"_id": 0}).to_list(100)
    
    pending = []
    for notif in notifications:
        should_send = False
        if notif['repeat'] == "none":
            if not notif.get('last_sent'):
                should_send = True
        elif notif['repeat'] == "daily":
            # Check if not already sent today
            last_sent = notif.get('last_sent')
            if not last_sent or last_sent[:10] != user_local.strftime("%Y-%m-%d"):
                should_send = True
        elif notif['repeat'] in ["weekly", "custom"]:
            if current_day in [d.lower() for d in notif.get('repeat_days', [])]:
                last_sent = notif.get('last_sent')
                if not last_sent or last_sent[:10] != user_local.strftime("%Y-%m-%d"):
                    should_send = True
        
        if should_send:
            pending.append(notif)
            # Mark as sent
            await db.notifications.update_one(
                {"notification_id": notif["notification_id"]},
                {"$set": {"last_sent": datetime.now(timezone.utc).isoformat()}}
            )
    
    return pending


# ========== REDAÇÃO (ESSAY) SECTION ==========





@api_router.post("/study/redacao/random-theme")
async def random_essay_theme(request: Request, data: dict = {}, session_token: Optional[str] = Cookie(None)):
    """Generate a random essay theme likely to appear in exams"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)

    concurso_type = data.get("concurso_type", "geral")

    prompt = f"""Sorteie UM tema de redação que tenha alta probabilidade de cair em provas de concurso público ({concurso_type}).
Responda APENAS com JSON:
{{
  "tema": "O tema completo da redação",
  "tipo_texto": "Dissertativo-Argumentativo",
  "banca_relacionada": "CESPE/CEBRASPE",
  "contexto": "Breve contexto sobre o tema e por que é relevante para concursos",
  "textos_motivadores": ["Texto motivador 1 (trecho real ou adaptado)", "Texto motivador 2"],
  "dicas": ["Dica para abordar este tema 1", "Dica 2"],
  "temas_relacionados": ["Tema relacionado 1", "Tema 2"],
  "nivel_dificuldade": "Médio"
}}

Use temas ATUAIS e RELEVANTES de {datetime.now().year}. Varie entre:
- Saúde pública, Educação, Tecnologia, Meio ambiente, Segurança, Direitos humanos, Economia, Cidadania digital"""

    try:
        response = await call_llm(prompt, f"essay_theme_{user.user_id}", "Você é especialista em redação para concursos públicos brasileiros.", user_id=user.user_id, task='assistant_chat')
        json_str = response.strip()
        if json_str.startswith("```json"): json_str = json_str[7:]
        if json_str.startswith("```"): json_str = json_str[3:]
        if json_str.endswith("```"): json_str = json_str[:-3]
        theme = json.loads(json_str.strip())
        return {"success": True, "theme": theme}
    except Exception:
        return {"success": True, "theme": {
            "tema": "O papel da tecnologia na promoção da inclusão social no Brasil",
            "tipo_texto": "Dissertativo-Argumentativo",
            "banca_relacionada": "Diversas",
            "contexto": "A transformação digital e seus impactos na sociedade brasileira",
            "textos_motivadores": ["A inclusão digital é fundamental para o exercício pleno da cidadania no século XXI."],
            "dicas": ["Aborde os desafios de acesso à tecnologia em regiões remotas", "Mencione políticas públicas existentes"],
            "temas_relacionados": ["Exclusão digital", "Direito à informação"],
            "nivel_dificuldade": "Médio"
        }}


# ========== GENERAL INTEGRATED CHAT ==========

@api_router.post("/chat/general")
async def general_integrated_chat(request: Request, data: dict, session_token: Optional[str] = Cookie(None)):
    body = AiChatRequest(message=data.get("content", ""), conversation_id=data.get("conversation_id", "primary"),
                         request_id=data.get("request_id") or uuid.uuid4().hex, page="/chat")
    result = await ai_chat(request, body, session_token)
    return {**result, "intent": "general", "saved_item": None}


@api_router.get("/chat/general/messages")
async def get_general_messages(request: Request, session_token: Optional[str] = Cookie(None)):
    result = await ai_conversation(request, "primary", session_token)
    return result["messages"]


@api_router.get("/chat/general/archive")
async def get_general_archive(request: Request, before: Optional[str] = None, session_token: Optional[str] = Cookie(None)):
    user = await get_current_user(authorization=request.headers.get('Authorization'), session_token=session_token)
    from services.conversations import Conversations
    return await Conversations().archive(user.user_id, before)


# ========== MONTHLY BILLS (CONTAS DO MÊS) ==========









# ========== WORKOUT IMPORT FROM FILE ==========



# ========== SAVED WORKOUT INSIGHTS ==========







# ========== AI MEAL PLAN GENERATION ==========






# ========== HEALTH CALCULATOR ==========
@api_router.post("/health/calculate")
async def calculate_health_metrics(request: Request, session_token: Optional[str] = Cookie(None)):
    """Calculate BMI, BMR, TDEE, and recommended macros"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    body = await request.json()
    weight = float(body.get("weight", 70))
    height = float(body.get("height", 170))  # cm
    age = int(body.get("age", 25))
    gender = body.get("gender", "male")  # male, female
    activity_level = body.get("activity_level", "moderate")  # sedentary, light, moderate, active, very_active
    objective = body.get("objective", "maintain")  # lose, maintain, gain
    
    # BMI
    height_m = height / 100
    bmi = round(weight / (height_m ** 2), 1)
    
    if bmi < 18.5:
        bmi_class = "Abaixo do peso"
    elif bmi < 25:
        bmi_class = "Peso normal"
    elif bmi < 30:
        bmi_class = "Sobrepeso"
    elif bmi < 35:
        bmi_class = "Obesidade grau I"
    elif bmi < 40:
        bmi_class = "Obesidade grau II"
    else:
        bmi_class = "Obesidade grau III"
    
    # BMR (Mifflin-St Jeor)
    if gender == "male":
        bmr = round(10 * weight + 6.25 * height - 5 * age + 5)
    else:
        bmr = round(10 * weight + 6.25 * height - 5 * age - 161)
    
    # TDEE
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }
    tdee = round(bmr * activity_multipliers.get(activity_level, 1.55))
    
    # Calorie target based on objective
    if objective == "lose":
        calories_target = tdee - 500
    elif objective == "gain":
        calories_target = tdee + 300
    else:
        calories_target = tdee
    
    # Macros
    if objective == "gain":
        protein_g = round(weight * 2.0)
        fat_g = round(weight * 1.0)
        carbs_g = round((calories_target - (protein_g * 4 + fat_g * 9)) / 4)
    elif objective == "lose":
        protein_g = round(weight * 2.2)
        fat_g = round(weight * 0.8)
        carbs_g = round((calories_target - (protein_g * 4 + fat_g * 9)) / 4)
    else:
        protein_g = round(weight * 1.6)
        fat_g = round(weight * 1.0)
        carbs_g = round((calories_target - (protein_g * 4 + fat_g * 9)) / 4)
    
    # Ideal weight range (BMI 18.5-24.9)
    ideal_weight_min = round(18.5 * (height_m ** 2), 1)
    ideal_weight_max = round(24.9 * (height_m ** 2), 1)
    
    # Water intake recommendation
    water_liters = round(weight * 0.035, 1)
    
    result = {
        "bmi": bmi,
        "bmi_class": bmi_class,
        "bmr": bmr,
        "tdee": tdee,
        "calories_target": calories_target,
        "macros": {
            "protein_g": max(protein_g, 0),
            "carbs_g": max(carbs_g, 0),
            "fat_g": max(fat_g, 0),
            "protein_pct": round(protein_g * 4 / max(calories_target, 1) * 100),
            "carbs_pct": round(max(carbs_g, 0) * 4 / max(calories_target, 1) * 100),
            "fat_pct": round(fat_g * 9 / max(calories_target, 1) * 100)
        },
        "ideal_weight": {"min": ideal_weight_min, "max": ideal_weight_max},
        "water_liters": water_liters,
        "objective": objective,
        "input": {"weight": weight, "height": height, "age": age, "gender": gender, "activity_level": activity_level}
    }
    
    return result


# ========== DASHBOARD WEEKLY SUMMARY ==========



# ========== UNIFIED STREAKS ==========


# ========== DAILY SUMMARY (AI) ==========



# ========== GLOBAL SEARCH ==========


# ========== SMART REMINDERS ==========


# ========== SHOPPING LIST FROM RECIPES ==========






# ========== UNIFIED CALENDAR ==========



# ========== CROSS-MODULE SUGGESTIONS ==========




# ===== EXPORT ENDPOINTS =====
from io import BytesIO
from fastapi.responses import StreamingResponse








# ========== TELEGRAM BOT INTEGRATION ==========
# import httpx
# import secrets
# from telegram import Bot, Update

# TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
telegram_bot = None
TELEGRAM_BOT_TOKEN = ''
TELEGRAM_BOT_WEBHOOK_SECRET = os.environ.get('TELEGRAM_BOT_WEBHOOK_SECRET', '')
# if TELEGRAM_BOT_TOKEN:
#     try:
#         telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN)
# except Exception as e:
#     logging.error(f"Failed to initialize Telegram bot: {e}")

@api_router.post("/telegram/setup-webhook")
async def setup_telegram_webhook(request: Request, session_token: Optional[str] = Cookie(None)):
    """Global bot configuration is only performed by the server at startup."""
    await get_current_user(
        authorization=request.headers.get("Authorization"), session_token=session_token
    )
    raise HTTPException(status_code=403, detail="Webhook configuration is managed by the server")

@api_router.post("/telegram/link")
async def link_telegram(request: Request, session_token: Optional[str] = Cookie(None)):
    """Generate a link code for the user to send to the Telegram bot"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    # Check if already linked
    existing = await db.telegram_links.find_one({"user_id": user.user_id, "status": "active"}, {"_id": 0})
    if existing:
        return {
            "already_linked": True,
            "chat_id": existing.get("chat_id"),
            "linked_at": existing.get("linked_at")
        }
    
    # Generate a 6-char code
    code = secrets.token_hex(3).upper()
    
    await db.telegram_link_codes.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "user_id": user.user_id,
            "code": code,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        }},
        upsert=True
    )
    
    bot_info = None
    if telegram_bot:
        try:
            async with httpx.AsyncClient() as hclient:
                resp = await hclient.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe")
                bot_data = resp.json()
                if bot_data.get("ok"):
                    bot_info = bot_data["result"]
        except Exception:
            pass
    
    bot_username = bot_info.get("username", "") if bot_info else ""
    
    return {
        "code": code,
        "expires_in_minutes": 10,
        "bot_username": bot_username,
        "bot_link": f"https://t.me/{bot_username}" if bot_username else "",
        "instructions": f"Envie /vincular {code} para o bot @{bot_username} no Telegram"
    }

@api_router.post("/telegram/unlink")
async def unlink_telegram(request: Request, session_token: Optional[str] = Cookie(None)):
    """Unlink Telegram account"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    result = await db.telegram_links.update_one(
        {"user_id": user.user_id, "status": "active"},
        {"$set": {"status": "inactive", "unlinked_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"success": True, "was_linked": result.modified_count > 0}

@api_router.get("/telegram/status")
async def get_telegram_status(request: Request, session_token: Optional[str] = Cookie(None)):
    """Check Telegram link status"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    link = await db.telegram_links.find_one({"user_id": user.user_id, "status": "active"}, {"_id": 0})
    
    bot_username = ""
    if telegram_bot:
        try:
            async with httpx.AsyncClient() as hclient:
                resp = await hclient.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe")
                bot_data = resp.json()
                if bot_data.get("ok"):
                    bot_username = bot_data["result"].get("username", "")
        except Exception:
            pass
    
    return {
        "linked": link is not None,
        "chat_id": link.get("chat_id") if link else None,
        "linked_at": link.get("linked_at") if link else None,
        "telegram_name": link.get("telegram_name") if link else None,
        "bot_username": bot_username,
        "bot_configured": bool(TELEGRAM_BOT_TOKEN)
    }

async def handle_telegram_message(chat_id: int, text: str, telegram_name: str = ""):
    """Process incoming Telegram messages"""
    import random
    
    text = text.strip()
    
    # /start command
    if text.startswith("/start"):
        welcome = (
            "🌟 *Bem-vindo ao Sirius Bot!*\n\n"
            "Eu sou seu assistente pessoal do Sirius. Aqui você pode:\n\n"
            "📝 *Registrar transações:*\n"
            "• `Gastei 50 no mercado`\n"
            "• `Recebi 3000 de salário`\n\n"
            "📊 *Consultar dados:*\n"
            "• /resumo - Resumo do dia\n"
            "• /saldo - Saldo atual\n"
            "• /metas - Progresso das metas\n\n"
            "🔗 *Vincular conta:*\n"
            "• /vincular CODIGO - Vincule com sua conta Sirius\n\n"
            "❓ /ajuda - Ver todos os comandos"
        )
        await send_telegram_message(chat_id, welcome, parse_mode="Markdown")
        return
    
    # /ajuda command
    if text.startswith("/ajuda") or text.startswith("/help"):
        help_text = (
            "📋 *Comandos disponíveis:*\n\n"
            "🔗 `/vincular CODIGO` - Vincular conta Sirius\n"
            "💰 `/saldo` - Ver saldo atual\n"
            "📊 `/resumo` - Resumo financeiro do dia\n"
            "🎯 `/metas` - Progresso das metas\n"
            "📅 `/mes` - Resumo do mês\n"
            "💪 `/frase` - Frase motivacional\n"
            "❓ `/ajuda` - Esta mensagem\n\n"
            "💡 *Dica:* Envie mensagens naturais como:\n"
            "• `Gastei 150 no supermercado`\n"
            "• `Recebi 500 de freelance`\n"
            "• `Paguei 200 de luz e 100 de água`"
        )
        await send_telegram_message(chat_id, help_text, parse_mode="Markdown")
        return
    
    # /vincular command
    if text.startswith("/vincular"):
        parts = text.split()
        if len(parts) < 2:
            await send_telegram_message(chat_id, "⚠️ Use: /vincular CODIGO\n\nGere o código no app Sirius em Configurações > Telegram.")
            return
        
        code = parts[1].upper()
        link_code = await db.telegram_link_codes.find_one({"code": code}, {"_id": 0})
        
        if not link_code:
            await send_telegram_message(chat_id, "❌ Código inválido ou expirado. Gere um novo código no app.")
            return
        
        # Check expiration
        expires_at = datetime.fromisoformat(link_code["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            await send_telegram_message(chat_id, "⏰ Código expirado. Gere um novo código no app.")
            await db.telegram_link_codes.delete_one({"code": code})
            return
        
        user_id = link_code["user_id"]
        
        # Deactivate any previous links
        await db.telegram_links.update_many(
            {"user_id": user_id, "status": "active"},
            {"$set": {"status": "inactive"}}
        )
        await db.telegram_links.update_many(
            {"chat_id": chat_id, "status": "active"},
            {"$set": {"status": "inactive"}}
        )
        
        # Create new link
        await db.telegram_links.insert_one({
            "user_id": user_id,
            "chat_id": chat_id,
            "telegram_name": telegram_name,
            "status": "active",
            "linked_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Delete used code
        await db.telegram_link_codes.delete_one({"code": code})
        
        # Get user info
        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        name = user_doc.get("name", "Usuário") if user_doc else "Usuário"
        
        await send_telegram_message(
            chat_id,
            f"✅ *Conta vinculada com sucesso!*\n\nOlá, {name}! 🎉\nAgora você pode registrar transações e consultar dados diretamente aqui no Telegram."
            , parse_mode="Markdown"
        )
        return
    
    # For all other commands/messages, check if linked
    link = await db.telegram_links.find_one({"chat_id": chat_id, "status": "active"}, {"_id": 0})
    if not link:
        await send_telegram_message(
            chat_id,
            "🔒 Você precisa vincular sua conta primeiro!\n\n"
            "1️⃣ Abra o app Sirius\n"
            "2️⃣ Vá em Configurações > Telegram\n"
            "3️⃣ Clique em 'Vincular'\n"
            "4️⃣ Envie aqui: /vincular CODIGO"
        )
        return
    
    user_id = link["user_id"]
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user_doc:
        await send_telegram_message(chat_id, "❌ Erro: usuário não encontrado.")
        return
    
    # /saldo command
    if text.startswith("/saldo"):
        today = datetime.now().strftime("%Y-%m-%d")
        month_start = datetime.now().strftime("%Y-%m-01")
        
        all_txns = await db.transactions.find({"user_id": user_id}).to_list(10000)
        total_income = sum(t.get("amount", 0) for t in all_txns if t.get("type") == "income")
        total_expense = sum(t.get("amount", 0) for t in all_txns if t.get("type") == "expense")
        balance = total_income - total_expense
        
        month_txns = [t for t in all_txns if t.get("date", "") >= month_start]
        month_income = sum(t.get("amount", 0) for t in month_txns if t.get("type") == "income")
        month_expense = sum(t.get("amount", 0) for t in month_txns if t.get("type") == "expense")
        
        emoji = "📈" if balance >= 0 else "📉"
        msg = (
            f"{emoji} *Seu Saldo*\n\n"
            f"💰 Saldo total: R$ {balance:,.2f}\n\n"
            f"📅 *Este mês:*\n"
            f"   ↗️ Receitas: R$ {month_income:,.2f}\n"
            f"   ↘️ Despesas: R$ {month_expense:,.2f}\n"
            f"   📊 Balanço: R$ {month_income - month_expense:,.2f}"
        )
        await send_telegram_message(chat_id, msg, parse_mode="Markdown")
        return
    
    # /resumo command
    if text.startswith("/resumo"):
        today = datetime.now().strftime("%Y-%m-%d")
        today_txns = await db.transactions.find({"user_id": user_id, "date": today}).to_list(100)
        
        if not today_txns:
            await send_telegram_message(chat_id, "📋 Nenhuma transação registrada hoje.\n\nEnvie algo como `Gastei 50 no almoço` para começar!")
            return
        
        incomes = [t for t in today_txns if t.get("type") == "income"]
        expenses = [t for t in today_txns if t.get("type") == "expense"]
        
        msg = f"📊 *Resumo de Hoje ({today})*\n\n"
        
        if incomes:
            total_in = sum(t.get("amount", 0) for t in incomes)
            msg += f"↗️ *Receitas:* R$ {total_in:,.2f}\n"
            for t in incomes:
                msg += f"   • {t.get('description', 'Sem descrição')} - R$ {t.get('amount', 0):,.2f}\n"
            msg += "\n"
        
        if expenses:
            total_exp = sum(t.get("amount", 0) for t in expenses)
            msg += f"↘️ *Despesas:* R$ {total_exp:,.2f}\n"
            for t in expenses:
                msg += f"   • {t.get('description', 'Sem descrição')} - R$ {t.get('amount', 0):,.2f}\n"
        
        await send_telegram_message(chat_id, msg, parse_mode="Markdown")
        return
    
    # /metas command
    if text.startswith("/metas"):
        goals = await db.goals.find({"user_id": user_id}).to_list(20)
        if not goals:
            await send_telegram_message(chat_id, "🎯 Nenhuma meta cadastrada.\nCrie metas no app Sirius!")
            return
        
        msg = "🎯 *Suas Metas*\n\n"
        for g in goals:
            progress = g.get("progress", 0)
            bar_filled = int(progress / 10)
            bar_empty = 10 - bar_filled
            bar = "█" * bar_filled + "░" * bar_empty
            msg += f"• {g.get('title', 'Meta')}\n  [{bar}] {progress}%\n\n"
        
        await send_telegram_message(chat_id, msg, parse_mode="Markdown")
        return
    
    # /mes command
    if text.startswith("/mes"):
        month_start = datetime.now().strftime("%Y-%m-01")
        month_txns = await db.transactions.find({
            "user_id": user_id,
            "date": {"$gte": month_start}
        }).to_list(1000)
        
        income = sum(t.get("amount", 0) for t in month_txns if t.get("type") == "income")
        expense = sum(t.get("amount", 0) for t in month_txns if t.get("type") == "expense")
        
        # Group expenses by category
        cat_totals = {}
        for t in month_txns:
            if t.get("type") == "expense":
                cat = t.get("category", "outros")
                cat_totals[cat] = cat_totals.get(cat, 0) + t.get("amount", 0)
        
        sorted_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
        
        msg = "📅 *Resumo do Mês*\n\n"
        msg += f"↗️ Receitas: R$ {income:,.2f}\n"
        msg += f"↘️ Despesas: R$ {expense:,.2f}\n"
        msg += f"📊 Balanço: R$ {income - expense:,.2f}\n\n"
        
        if sorted_cats:
            msg += "*Top despesas por categoria:*\n"
            for cat, total in sorted_cats[:5]:
                pct = (total / expense * 100) if expense > 0 else 0
                msg += f"   • {cat.title()}: R$ {total:,.2f} ({pct:.0f}%)\n"
        
        await send_telegram_message(chat_id, msg, parse_mode="Markdown")
        return
    
    # /frase command
    if text.startswith("/frase"):
        fallback_quotes = [
            "🔥 A dor do treino é temporária. A dor do arrependimento é permanente.",
            "⚔️ Guerreiros não nascem. São forjados no fogo da disciplina diária.",
            "🦁 Seja a pessoa que você precisava quando era mais novo.",
            "💎 Diamantes são apenas pedras que não desistiram sob pressão.",
            "🎯 Enquanto outros dormem, você constrói seu império.",
            "⚡ Sua única competição é quem você era ontem.",
            "🏆 Champions são feitos quando ninguém está olhando.",
            "🚀 Conforto é a morte lenta dos seus sonhos. Acorde!",
            "💪 Seu corpo pode quase tudo. É sua mente que você precisa convencer.",
            "🌟 A excelência não é um ato, é um hábito."
        ]
        try:
            quote_resp = await call_llm(
                "Gere UMA frase motivacional curta, impactante e única. Use 1-2 emojis. Máximo 2 linhas. Responda APENAS com a frase.",
                f"tg_motivation_{user_id}",
                "Você é um mestre motivacional."
            , task='assistant_chat')
            await send_telegram_message(chat_id, quote_resp.strip())
        except Exception:
            await send_telegram_message(chat_id, random.choice(fallback_quotes))
        return
    
    # Natural language transaction registration
    # Check if it looks like a transaction
    prompt = f"""Analise esta mensagem e determine se é um registro de transação financeira.
Mensagem: "{text}"

Se for uma ou mais transações, responda APENAS com um JSON array:
[{{"type": "income" ou "expense", "amount": valor_numerico, "description": "descrição curta", "category": "categoria"}}]

Categorias válidas: alimentação, transporte, moradia, saúde, educação, lazer, vestuário, investimentos, salário, freelance, outros

Se NÃO for uma transação, responda EXATAMENTE: NOT_TRANSACTION

Responda APENAS com o JSON array ou NOT_TRANSACTION, sem explicações."""

    try:
        ai_response = await call_llm(prompt, f"tg_parse_{user_id}", "Você é um parser de transações financeiras. Extraia dados com precisão.", task='assistant_chat')
        ai_response = ai_response.strip()
        
        if "NOT_TRANSACTION" in ai_response:
            # General chat response
            chat_prompt = f"O usuário disse: '{text}'. Responda de forma breve e útil como assistente financeiro do Sirius. Máximo 3 linhas."
            chat_resp = await call_llm(chat_prompt, f"tg_chat_{user_id}", "Você é o assistente do Sirius, focado em finanças, produtividade e saúde.", task='assistant_chat')
            await send_telegram_message(chat_id, chat_resp.strip())
            return
        
        # Parse JSON
        clean = ai_response.replace("```json", "").replace("```", "").strip()
        transactions = json.loads(clean)
        if not isinstance(transactions, list):
            transactions = [transactions]
        
        registered = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        for txn in transactions:
            txn_id = f"txn_{uuid.uuid4().hex[:12]}"
            txn_doc = {
                "transaction_id": txn_id,
                "user_id": user_id,
                "type": txn.get("type", "expense"),
                "amount": float(txn.get("amount", 0)),
                "description": txn.get("description", "Sem descrição"),
                "category": txn.get("category", "outros"),
                "date": today,
                "source": "telegram",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.transactions.insert_one(txn_doc)
            registered.append(txn_doc)
        
        if len(registered) == 1:
            t = registered[0]
            emoji = "↗️" if t["type"] == "income" else "↘️"
            msg = f"✅ Registrado!\n\n{emoji} {t['description']}\n💰 R$ {t['amount']:,.2f}\n📂 {t['category'].title()}"
        else:
            total = sum(t["amount"] for t in registered)
            msg = f"✅ {len(registered)} transações registradas!\n\n"
            for i, t in enumerate(registered, 1):
                emoji = "↗️" if t["type"] == "income" else "↘️"
                msg += f"{i}. {emoji} {t['description']} - R$ {t['amount']:,.2f}\n"
            msg += f"\n💰 Total: R$ {total:,.2f}"
        
        await send_telegram_message(chat_id, msg)
    
    except json.JSONDecodeError:
        await send_telegram_message(chat_id, "🤖 Não consegui entender. Tente algo como:\n• `Gastei 50 no mercado`\n• `Recebi 3000 de salário`\n• /ajuda")
    except Exception as e:
        logging.error(f"Telegram message handling error: {e}")
        await send_telegram_message(chat_id, "⚠️ Ocorreu um erro. Tente novamente em instantes.")

async def send_telegram_message(chat_id: int, text: str, parse_mode: str = None):
    """Send a message via Telegram Bot API"""
    try:
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        async with httpx.AsyncClient() as hclient:
            resp = await hclient.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=10
            )
            result = resp.json()
            if not result.get("ok"):
                # Retry without parse_mode if Markdown failed
                if parse_mode:
                    payload.pop("parse_mode")
                    await hclient.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json=payload,
                        timeout=10
                    )
            return result
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")

async def send_telegram_daily_summary(user_id: str, chat_id: int):
    """Send daily summary to a linked Telegram user"""
    today = datetime.now().strftime("%Y-%m-%d")
    txns = await db.transactions.find({"user_id": user_id, "date": today}).to_list(100)
    
    if not txns:
        return
    
    incomes = sum(t.get("amount", 0) for t in txns if t.get("type") == "income")
    expenses = sum(t.get("amount", 0) for t in txns if t.get("type") == "expense")
    
    msg = f"🌙 *Resumo do dia ({today})*\n\n"
    msg += f"↗️ Receitas: R$ {incomes:,.2f}\n"
    msg += f"↘️ Despesas: R$ {expenses:,.2f}\n"
    msg += f"📊 Balanço do dia: R$ {incomes - expenses:,.2f}\n\n"
    msg += f"📝 {len(txns)} transações registradas"
    
    await send_telegram_message(chat_id, msg, parse_mode="Markdown")

# Telegram webhook endpoint (no auth required - Telegram calls this)
@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive updates authenticated with a dedicated Telegram webhook secret."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_BOT_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Telegram is not configured")
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secrets.compare_digest(supplied.encode("utf-8"), TELEGRAM_BOT_WEBHOOK_SECRET.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    
    try:
        update_data = await request.json()
        message = update_data.get("message", {})
        
        if not message:
            return {"ok": True}
        
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        first_name = message.get("from", {}).get("first_name", "")
        username = message.get("from", {}).get("username", "")
        telegram_name = first_name or username
        
        if chat_id and text:
            # Handle in background to respond quickly
            import asyncio
            asyncio.create_task(handle_telegram_message(chat_id, text, telegram_name))
        
        return {"ok": True}
    except Exception as e:
        logging.error(f"Telegram webhook error: {e}")
        return {"ok": True}  # Always return 200 to Telegram

@api_router.post("/telegram/send-daily-summaries")
async def trigger_daily_summaries(request: Request, session_token: Optional[str] = Cookie(None)):
    """Trigger daily summaries only for the authenticated user."""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    links = await db.telegram_links.find({"status": "active", "user_id": user.user_id}).to_list(1000)
    sent = 0
    for link in links:
        try:
            await send_telegram_daily_summary(link["user_id"], link["chat_id"])
            sent += 1
        except Exception as e:
            logging.error(f"Failed to send summary to {link.get('chat_id')}: {e}")
    
    return {"sent": sent, "total": len(links)}


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    conversation_id: str = Field(default="primary", min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=8, max_length=80)
    page: str = Field(default="", max_length=200)
    page_context: str = Field(default="", max_length=2000)

async def build_ai_system_prompt(user_id: str, page: str = "", page_context: str = "") -> str:
    from assistant_service import context_prompt
    return await context_prompt(user_id, page, page_context)

@api_router.get("/ai/conversation")
async def ai_conversation(request: Request, conversation_id: str = "primary", session_token: Optional[str] = Cookie(None)):
    user = await get_current_user(authorization=request.headers.get("Authorization"), session_token=session_token)
    from services.conversations import Conversations
    return await Conversations().read(user.user_id, conversation_id)

@api_router.post("/ai/chat")
async def ai_chat(request: Request, body: AiChatRequest, session_token: Optional[str] = Cookie(None)):
    user = await get_current_user(authorization=request.headers.get("Authorization"), session_token=session_token)
    return await agent_runtime.chat(user.user_id, body)


from ai.routes import AgentRuntime
agent_runtime = AgentRuntime(get_current_user)
api_router.include_router(agent_runtime.api)
from services.gamification import router as gamification_router
api_router.include_router(gamification_router)
from services.quotes_alerts import router as quotes_alerts_router
api_router.include_router(quotes_alerts_router)
from gemini_service import configure as configure_ai_compatibility
configure_ai_compatibility(agent_runtime.router)

from services.study_workspace import router as workspace_router
api_router.include_router(workspace_router)
from services import edital_import_routes
edital_import_routes.configure(get_current_user,call_llm,call_gemini,get_user_api_key,_hydrate_disciplinas_from_text,extract_pdf_text)
api_router.include_router(edital_import_routes.router)
from services.study_schedule_routes import router as study_schedule_router
api_router.include_router(study_schedule_router)
from services import exam_generation_routes
exam_generation_routes.configure(get_current_user,get_user_api_key,request_gemini,upload_gemini_path,gemini_file_part)
api_router.include_router(exam_generation_routes.router)
from services.exam_routes import router as exam_sql_router
api_router.include_router(exam_sql_router)
from services import study_cards,study_quizzes
study_cards.configure(call_llm)
api_router.include_router(study_cards.router)
api_router.include_router(study_quizzes.router)
from services import study_tasks,study_statistics
api_router.include_router(study_tasks.router)
api_router.include_router(study_statistics.router)
from services import study_history_routes
api_router.include_router(study_history_routes.router)
from services import study_material_routes
study_material_routes.configure(get_user_api_key,request_gemini,upload_gemini_path,gemini_file_part)
api_router.include_router(study_material_routes.router)
from services import study_pdf_materials
api_router.include_router(study_pdf_materials.router)
from services import workout_session_routes
api_router.include_router(workout_session_routes.router)
from services import workout_plan_routes
api_router.include_router(workout_plan_routes.router)
from services import workout_logs
api_router.include_router(workout_logs.router)
from services import workout_daily_routes
api_router.include_router(workout_daily_routes.router)
from services import body_measurements,health_ai_routes
api_router.include_router(body_measurements.router)
from services import nutrition
api_router.include_router(nutrition.router)
from services import recipe_routes,recipe_generation_routes
recipe_generation_routes.configure(get_current_user,get_user_api_key,request_gemini)
api_router.include_router(recipe_generation_routes.api_router)
api_router.include_router(recipe_routes.router)
from services import nutrition_plans,nutrition_generation_routes
nutrition_generation_routes.configure(get_current_user,get_user_api_key,request_gemini)
api_router.include_router(nutrition_generation_routes.api_router)
api_router.include_router(nutrition_plans.router)
from services import nutrition_shopping
api_router.include_router(nutrition_shopping.router)
from services import domain_exports
api_router.include_router(domain_exports.router)
from services import reports
reports.configure(call_llm)
api_router.include_router(reports.router)
from services import dashboard
api_router.include_router(dashboard.router)
from services import global_search
api_router.include_router(global_search.router)
from services import dashboard_panels,daily_briefing
daily_briefing.configure(call_llm)
api_router.include_router(dashboard_panels.router)
api_router.include_router(daily_briefing.router)
health_ai_routes.configure(get_current_user,call_llm,request_gemini)
api_router.include_router(health_ai_routes.api_router)
from services import workout_history_routes
api_router.include_router(workout_history_routes.router)
from services import workout_generation_routes
workout_generation_routes.configure(get_current_user,call_llm,get_user_api_key,request_gemini)
api_router.include_router(workout_generation_routes.api_router)
from services.edital_routes import router as edital_sql_router
api_router.include_router(edital_sql_router)
from services.studies_v2_routes import router as studies_v2_router
api_router.include_router(studies_v2_router)
from contest_watch import ContestWatcher
contest_watcher = ContestWatcher(db, get_current_user)
api_router.include_router(contest_watcher.router)
from edital_review_routes import review_router
api_router.include_router(review_router(get_current_user))
from edital_jobs import EditalJobs

async def process_queued_edital(user_id, file, force):
    from types import SimpleNamespace
    return await process_edital_analysis(SimpleNamespace(user_id=user_id), file, force)

edital_jobs = EditalJobs(get_current_user, process_queued_edital)
api_router.include_router(edital_jobs.router)

from operations import install_request_metrics, ensure_query_indexes
install_request_metrics(app)

# Authentication is served by PostgreSQL repositories.
from services.auth_routes import router as auth_router
api_router.include_router(auth_router)
from services.planning_routes import router as planning_router
api_router.include_router(planning_router)
from services.goals_routes import router as goals_router
api_router.include_router(goals_router)
from services.studies_catalog_routes import router as studies_catalog_router
api_router.include_router(studies_catalog_router)
from services.study_activity_routes import router as study_activity_router
api_router.include_router(study_activity_router)
from services.finance_routes import router as finance_router, configure_ai as configure_finance_ai
from services.finance_export import router as finance_export_router
configure_finance_ai(call_llm)
api_router.include_router(finance_router)
api_router.include_router(finance_export_router)

# Include router AFTER all endpoints are defined
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_activity_storage():
    await setup_activity_collections()
    await ensure_query_indexes(db)
    await agent_runtime.setup()
    await db.study_targets.create_index([('user_id', 1), ('program_id', 1)], unique=True)
    await db.study_attempts.create_index([('user_id', 1), ('program_id', 1), ('created_at', -1)])
    await db.study_attempts.create_index([('user_id', 1), ('notebook_id', 1), ('topic_key', 1)])
    await contest_watcher.setup()
    await edital_jobs.start()


@app.on_event("startup")
async def startup_setup():
    """Configure Telegram from trusted server settings only."""
    if not TELEGRAM_BOT_TOKEN:
        return
    from urllib.parse import urlsplit
    import re
    backend_url = os.environ.get("BACKEND_PUBLIC_URL", "").rstrip("/")
    try:
        parsed = urlsplit(backend_url)
        valid_url = (parsed.scheme == "https" and parsed.hostname and
                     not parsed.username and not parsed.password and
                     not parsed.query and not parsed.fragment)
    except ValueError:
        valid_url = False
    if not valid_url or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", TELEGRAM_BOT_WEBHOOK_SECRET):
        logging.warning("Telegram webhook requires BACKEND_PUBLIC_URL (HTTPS) and TELEGRAM_BOT_WEBHOOK_SECRET (32-256 safe characters)")
        return
    try:
        async with httpx.AsyncClient() as hclient:
            resp = await hclient.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
                json={
                    "url": f"{backend_url}/api/telegram/webhook",
                    "secret_token": TELEGRAM_BOT_WEBHOOK_SECRET,
                    "allowed_updates": ["message"],
                },
                timeout=10,
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                logging.info("Telegram webhook configured")
            else:
                logging.warning("Telegram webhook configuration failed (HTTP %s)", resp.status_code)
    except Exception:
        # HTTP exception strings may contain the bot token in the request URL.
        logging.warning("Telegram webhook configuration failed")


@app.on_event("shutdown")
async def shutdown_db_client():
    await contest_watcher.close()
    await agent_runtime.automations.stop()
    from gemini_service import close
    await close()
    await edital_jobs.stop()
    client.close()
