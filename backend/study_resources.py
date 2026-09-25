"""Study priorities explain their inputs; public lessons come from YouTube, not the LLM."""
import asyncio
import html
import math
import re
import time
from urllib.parse import urlencode

import httpx


def positive_number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result > 0 else None
    except (TypeError, ValueError):
        return None


def normalize_content(content, topics=(), preserve_keys=False):
    if isinstance(content, str):
        content = [content]
    result = []
    for index, item in enumerate(content or topics or []):
        if isinstance(item, str):
            item = {"assunto": item}
        if not isinstance(item, dict) or not isinstance(item.get("assunto"), str):
            continue
        subs = item.get("subtopicos") or []
        if isinstance(subs, str):
            subs = [subs]
        if not isinstance(subs, list):
            subs = []
        row = {"assunto": item["assunto"], "subtopicos": [s for s in subs if isinstance(s, str)]}
        if preserve_keys:
            row["topic_key"] = str(index)
            row["subtopic_keys"] = [f"{index}_{i}" for i, sub in enumerate(subs) if isinstance(sub, str)]
        result.append(row)
    return result


def scoring_evidence(discipline, pdf_text):
    evidence = {}
    source = " ".join((pdf_text or "").casefold().split())
    for field in ("peso", "num_questoes"):
        quote = str(discipline.get(f"{field}_fonte") or "").strip()
        # A matching excerpt is traceability, not automatic certification of the AI's interpretation.
        matched = bool(quote and " ".join(quote.casefold().split()) in source)
        evidence[f"{field}_fonte"] = quote if matched else ""
        evidence[f"{field}_status"] = "extraido_com_fonte" if matched and positive_number(discipline.get(field)) else "a_conferir"
    return evidence


def sourced_deadlines(deadlines, pdf_text):
    """Keep literal dates with traceable source excerpts; not a certification of interpretation."""
    source = " ".join((pdf_text or "").casefold().split())
    result = []
    for item in deadlines if isinstance(deadlines, list) else []:
        if not isinstance(item, dict):
            continue
        label, date, quote = (str(item.get(key) or "").strip() for key in ("label", "data", "fonte"))
        normalized_quote = " ".join(quote.casefold().split())
        if label and date and normalized_quote and normalized_quote in source and " ".join(date.casefold().split()) in normalized_quote:
            result.append({"label": label, "data": date, "fonte": quote})
    return result


def prioritize(disciplines):
    scores = []
    # Never mix question-weight products with weight-only scores in the same ranking.
    complete_questions = all(positive_number(d.get("num_questoes")) for d in disciplines)
    for disc in disciplines:
        weight = positive_number(disc.get("peso")) or 1
        questions = positive_number(disc.get("num_questoes"))
        score = weight * questions if complete_questions else weight
        disc["prioridade_base"] = "peso × questões" if complete_questions else "peso disponível (questões incompletas)"
        disc["prioridade_provisoria"] = disc.get("peso_status") != "extraido_com_fonte" or (complete_questions and disc.get("num_questoes_status") != "extraido_com_fonte")
        disc["prioridade_score"] = score
        scores.append(score)
    maximum = max(scores, default=1)
    total = sum(scores)
    for disc in disciplines:
        ratio = disc["prioridade_score"] / maximum
        disc["prioridade"] = "alta" if ratio >= .75 else "media" if ratio >= .4 else "baixa"
        disc["participacao_estimada"] = round(100 * disc["prioridade_score"] / total, 1) if total else 0
    return sorted(disciplines, key=lambda d: d["prioridade_score"], reverse=True)


_lesson_cache = {}
_lesson_lock = asyncio.Lock()


async def youtube_lessons(query, api_key):
    fallback = "https://www.youtube.com/results?" + urlencode({"search_query": query})
    base = {"query": query, "search_url": fallback, "videos": []}
    if not api_key:
        return dict(base, status="not_configured", message="A busca de aulas ainda não está ativada. Você pode pesquisar este assunto no YouTube.")
    async with _lesson_lock:
        cached = _lesson_cache.get(query)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get("https://www.googleapis.com/youtube/v3/search", params={
                    "part": "snippet", "type": "video", "maxResults": 5, "q": query,
                    "relevanceLanguage": "pt", "regionCode": "BR", "safeSearch": "moderate",
                }, headers={"X-Goog-Api-Key": api_key})
            if response.status_code != 200:
                return dict(base, status="unavailable", message="A busca de aulas está indisponível no momento. Use a pesquisa no YouTube.")
            videos = []
            for item in response.json().get("items", []):
                video_id = item.get("id", {}).get("videoId", "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                    continue
                snippet = item.get("snippet", {})
                videos.append({"video_id": video_id, "title": html.unescape(snippet.get("title", "")),
                               "channel": html.unescape(snippet.get("channelTitle", "")),
                               "url": f"https://www.youtube.com/watch?v={video_id}"})
            result = dict(base, status="ok", videos=videos)
            if len(_lesson_cache) >= 128:
                _lesson_cache.pop(next(iter(_lesson_cache)))
            _lesson_cache[query] = (time.monotonic() + 3600, result)
            return result
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return dict(base, status="unavailable", message="Não foi possível buscar aulas agora. Use a pesquisa no YouTube.")
