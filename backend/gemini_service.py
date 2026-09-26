"""One asynchronous Gemini transport for text, structured output and files.

REST contract: https://ai.google.dev/api/generate-content and /api/files.
No SDK client and no blocking HTTP requests.
"""
import asyncio
import base64
import logging
import json
import uuid
import httpx
from typing import Optional, Dict, Any

GEMINI_MODEL = "gemini-2.5-flash"
_http = None

def http_client():
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(follow_redirects=False)
    return _http

async def close():
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None

async def record_usage(callback, *args, **kwargs):
    if callback:
        await callback(*args, **kwargs)

async def call_gemini(prompt: str, system_message: str, api_key: str, timeout_override: Optional[int] = None, user_id: Optional[str] = None, response_schema: Optional[dict] = None, usage_callback=None, parts=None, config_options=None) -> tuple[Optional[str], Optional[str]]:
    """Call Gemini API, returns (response_text, error_type).
    error_type: None on success, 'quota' on 429, 'invalid' on 400/401/403, 'other' otherwise.
    If `user_id` is provided, successful calls are counted in `db.gemini_usage` for quota tracking.
    If `response_schema` is provided, uses Structured Output (responseMimeType=application/json)."""
    from urllib.parse import quote
    models_to_try = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]
    if GEMINI_MODEL not in models_to_try:
        models_to_try.insert(0, GEMINI_MODEL)
    
    def _build_payload(model: str, include_schema: bool) -> dict:
        p: dict = {"contents": [{"role": "user", "parts": parts or [{"text": prompt}]}]}
        if config_options:
            p['generationConfig'] = dict(config_options)
        if system_message:
            p["systemInstruction"] = {"parts": [{"text": system_message}]}
        if include_schema and response_schema is not None:
            p["generationConfig"] = {**p.get('generationConfig', {}),
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            }
        return p

    last_error = None
    for model in models_to_try:
        timeout = timeout_override or (90 if "2.5" in model else 30)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={quote(api_key)}"
        
        for attempt in range(2):
            include_schema = (attempt == 0 and response_schema is not None)
            try:
                payload = _build_payload(model, include_schema)
                resp = await http_client().post( url, json=payload, timeout=timeout)
                logging.info(f"Gemini call (model={model} schema={include_schema} timeout={timeout}s): status={resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if text:
                        if user_id:
                            await record_usage(usage_callback, user_id, model, usage=data.get("usageMetadata"))
                        return text, None
                    logging.warning(f"Gemini 200 OK but no text in response (model={model})")
                else:
                    logging.error(f"Gemini API error (model={model}): {resp.status_code} - [provider body omitted]")
                if resp.status_code in (400, 401, 403) and include_schema:
                    logging.warning(f"Gemini {model} rejeitou schema — tentando sem schema")
                    continue
                if resp.status_code in (400, 401, 403):
                    return None, "invalid"
                if resp.status_code == 429:
                    last_error = "quota"
                    break
                last_error = "other"
                break
            except Exception as e:
                logging.error(f"Gemini error (model={model}): {type(e).__name__}")
                last_error = "other"
                break
    return None, last_error

async def upload_to_gemini(pdf_content: bytes, api_key: str, mime_type="application/pdf") -> Optional[str]:
    """Upload a PDF to Gemini's file API using multipart/form-data (like curl -F) and return the file URI."""
    import uuid
    from urllib.parse import quote
    upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={quote(api_key)}"
    
    boundary = f"---{uuid.uuid4().hex}"
    
    metadata = b'{"file":{"display_name":"edital.pdf"}}'
    
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="metadata"\r\n')
    parts.append(b'Content-Type: application/json; charset=UTF-8\r\n\r\n')
    parts.append(metadata)
    parts.append(b'\r\n')
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="media"; filename="edital.pdf"\r\n')
    parts.append(f'Content-Type: {mime_type}\r\n\r\n'.encode())
    parts.append(pdf_content)
    parts.append(b'\r\n')
    parts.append(f"--{boundary}--\r\n".encode())
    
    body = b"".join(parts)
    
    try:
        resp = await http_client().post( 
            upload_url,
            content=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=120
        )
        if resp.status_code == 200:
            data = resp.json()
            file_uri = data.get("file", {}).get("uri")
            file_name = data.get("file", {}).get("name", "")
            file_state = data.get("file", {}).get("state", "PROCESSING")
            logging.info(f"Gemini file upload success: {file_uri} (state={file_state})")
            
            # Poll until file is ACTIVE
            file_get_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={quote(api_key)}"
            for attempt in range(10):
                if file_state == "ACTIVE":
                    break
                await asyncio.sleep(2)
                try:
                    sr = await http_client().get( file_get_url, timeout=15)
                    if sr.status_code == 200:
                        file_state = sr.json().get("file", {}).get("state", "PROCESSING")
                        logging.info(f"Gemini file poll attempt {attempt+1}: state={file_state}")
                except Exception:
                    pass
            
            if file_state != "ACTIVE":
                logging.error(f"Gemini file never became ACTIVE, final state: {file_state}")
                return None
            
            return file_uri if file_state == "ACTIVE" else None
        logging.error(f"Gemini file upload failed: {resp.status_code} - {resp.text[:2000]}")
    except Exception as e:
        logging.error(f"Gemini file upload error: {type(e).__name__}")
    return None

async def call_gemini_with_pdf(pdf_content: bytes, prompt_text: str, system_message: str, api_key: str, timeout: int = 120, response_schema: Optional[dict] = None, user_id: Optional[str] = None, inline_max_bytes: int = 15 * 1024 * 1024, usage_callback=None) -> tuple[Optional[str], Optional[str]]:
    """Upload a PDF and call Gemini with the file. Returns (response_text, error_type).
    Tries current free-tier models in order (2.5-flash preferred; 2.5-flash-lite has largest daily free quota).
    When `response_schema` is passed, Gemini is forced to return JSON matching that schema (Structured Output).
    If `user_id` is provided, successful calls are counted in `db.gemini_usage`.

    Performance: for PDFs ≤ `inline_max_bytes` (default 15 MB) we send the PDF INLINE (base64)
    in a single request, avoiding the separate `/upload/v1beta/files` roundtrip (economiza ~5–25 s
    dependendo do tamanho e latência de rede). Above the threshold we fall back to the Files API.
    """
    import base64
    from urllib.parse import quote

    inline_ok = len(pdf_content) <= inline_max_bytes
    file_uri: Optional[str] = None
    if not inline_ok:
        file_uri = await upload_to_gemini(pdf_content, api_key)
        if not file_uri:
            return None, "other"

    # Build the PDF part once
    if inline_ok:
        pdf_part = {"inlineData": {"mimeType": "application/pdf", "data": base64.b64encode(pdf_content).decode("ascii")}}
        logging.info(f"Gemini PDF: sending INLINE ({len(pdf_content)/1024:.0f} KB) — sem upload API")
    else:
        pdf_part = {"fileData": {"mimeType": "application/pdf", "fileUri": file_uri}}
        logging.info(f"Gemini PDF: sending via FILE URI ({len(pdf_content)/1024/1024:.1f} MB)")

    # gemini-1.5-flash was retired by Google and now returns 404.
    # gemini-2.0-flash / 2.0-flash-lite often hit 429 (very low free-tier daily quota).
    # We prefer 2.5-flash (best quality) and the "latest" aliases which Google keeps updated
    # (gemini-flash-lite-latest has the highest free-tier daily quota).
    #
    # IMPORTANTE: `thinkingConfig` só é aceito por modelos da família 2.5 (gemini-2.5-flash,
    # gemini-2.5-pro). Enviar esse campo para `flash-latest`/`flash-lite-latest` retorna
    # 400 INVALID_ARGUMENT. Por isso montamos o payload por modelo.
    models_to_try = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]

    def _build_payload(model: str, include_schema: bool, include_thinking: bool) -> Dict[str, Any]:
        gc: Dict[str, Any] = {
            "temperature": 0,
            "maxOutputTokens": 65536,
        }
        if include_thinking and model.startswith("gemini-2.5"):
            # thinkingBudget=0 desliga o "thinking" no 2.5-flash → ~3-5x mais rápido
            gc["thinkingConfig"] = {"thinkingBudget": 0}
        if include_schema and response_schema is not None:
            gc["responseMimeType"] = "application/json"
            gc["responseSchema"] = response_schema
        p: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt_text}, pdf_part]}],
            "generationConfig": gc,
        }
        if system_message:
            p["systemInstruction"] = {"parts": [{"text": system_message}]}
        return p

    def _extract_text_and_finish(resp_json: dict) -> tuple[str, str, int]:
        candidate = (resp_json.get("candidates") or [{}])[0]
        finish = candidate.get("finishReason", "?")
        parts = ((candidate.get("content") or {}).get("parts") or [])
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        return text, finish, len(parts)

    for i, model in enumerate(models_to_try):
        # Timeouts agressivos por modelo: 2.5-flash falha rápido, flash-latest muitas vezes
        # demora além do normal para PDFs grandes, flash-lite-latest ganha tempo extra.
        if "2.5" in model:
            model_timeout = min(timeout, 30)
        elif "flash-latest" in model and "lite" not in model:
            model_timeout = min(timeout, 30)
        else:
            model_timeout = timeout
        # Cada modelo tem até 2 tentativas: (1) payload completo; (2) sem schema/thinking se der 400.
        for attempt in range(2):
            include_schema = (attempt == 0)
            include_thinking = (attempt == 0)
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={quote(api_key)}"
                payload = _build_payload(model, include_schema, include_thinking)
                resp = await http_client().post( url, json=payload, timeout=model_timeout)
                logging.info(
                    f"Gemini PDF call (model={model}, attempt={attempt+1}, schema={include_schema}, "
                    f"thinking={include_thinking}, timeout={model_timeout}s): status={resp.status_code}"
                )

                if resp.status_code == 200:
                    text, finish_reason, n_parts = _extract_text_and_finish(resp.json())
                    logging.info(f"Gemini PDF 200: model={model} finish={finish_reason} text_len={len(text)} parts={n_parts}")
                    if finish_reason == "MAX_TOKENS":
                        logging.warning(f"Gemini PDF response TRUNCATED (MAX_TOKENS) model={model}, trying next model...")
                        if i == len(models_to_try) - 1:
                            if text:
                                if user_id: await record_usage(usage_callback, user_id, model, usage=resp.json().get("usageMetadata"), feature="pdf")
                                return text, "truncated"
                            return None, "truncated"
                        break  # sai do loop de attempts e tenta o próximo modelo
                    if text:
                        if user_id: await record_usage(usage_callback, user_id, model, usage=resp.json().get("usageMetadata"), feature="pdf")
                        return text, None
                    # 200 sem texto (safety filter). Tenta próximo modelo.
                    logging.warning(f"Gemini PDF 200 but empty text (model={model}, finish={finish_reason}). Body: [provider body omitted]")
                    if i == len(models_to_try) - 1:
                        return None, "empty"
                    break

                elif resp.status_code == 400:
                    # INVALID_ARGUMENT — geralmente causado por campo não suportado no generationConfig
                    # (ex: thinkingConfig em flash-latest ou responseSchema muito complexo).
                    body = "provider rejected request"
                    logging.warning(f"Gemini PDF 400 (model={model}, attempt={attempt+1}): {body}")
                    if attempt == 0:
                        # Retry sem thinkingConfig e sem responseSchema no mesmo modelo
                        logging.info(f"Gemini PDF: retry model={model} sem thinkingConfig/responseSchema...")
                        continue
                    # Segunda tentativa também deu 400 → chave inválida ou modelo indisponível
                    if i == len(models_to_try) - 1:
                        logging.error(f"Gemini PDF: todos os modelos rejeitaram (última: {model}). Último body: {body}")
                        return None, "invalid"
                    break  # próximo modelo

                elif resp.status_code in (401, 403):
                    logging.error(f"Gemini PDF auth error (model={model}): {resp.status_code} - [provider body omitted]")
                    return None, "invalid"

                elif resp.status_code == 404:
                    # Modelo não disponível para essa chave/região — tenta o próximo modelo
                    logging.warning(f"Gemini PDF 404 model={model} (indisponível p/ esta chave), trying next...")
                    if i == len(models_to_try) - 1:
                        return None, "invalid"
                    break

                elif resp.status_code == 429:
                    if i == len(models_to_try) - 1:
                        return None, "quota"
                    logging.warning(f"Gemini PDF quota model={model}, trying next...")
                    break

                else:
                    if i == len(models_to_try) - 1:
                        logging.error(f"Gemini PDF API error (model={model}): {resp.status_code} - [provider body omitted]")
                        return None, "other"
                    logging.warning(f"Gemini PDF fail model={model}: {resp.status_code}, trying next...")
                    break
            except httpx.TimeoutException:
                if i == len(models_to_try) - 1:
                    logging.error("Gemini PDF timeout for all models")
                    return None, "timeout"
                logging.warning(f"Gemini PDF timeout model={model}, trying next...")
                break
            except Exception as e:
                if i == len(models_to_try) - 1:
                    logging.error(f"Gemini PDF call error (model={model}): {type(e).__name__}", exc_info=True)
                    return None, "other"
                logging.warning(f"Gemini PDF error model={model}: {type(e).__name__}, trying next...")
                break

    return None, "other"
