from typing import Optional
import unicodedata
from fastapi import APIRouter, Request, Cookie, HTTPException
from services.auth_routes import account
from services import edital_analyses as analyses
from edital_quality import mark_discipline_quality

router=APIRouter()

@router.get('/study/programs/editais')
async def list_editais(request: Request):
    user=await account(request)
    return await analyses.list_owned(user['user_id'])

@router.get('/study/programs/editais/{analysis_id}')
async def get_edital_analysis(request: Request, analysis_id: str):
    user=await account(request)
    result=await analyses.get(user['user_id'],analysis_id)
    mark_discipline_quality(result.get('cargos',[]))
    return result

@router.delete('/study/programs/editais/{analysis_id}')
async def delete_edital_analysis(request: Request, analysis_id: str):
    user=await account(request)
    return await analyses.remove(user['user_id'],analysis_id)

@router.post("/study/programs/editais/compare")
async def compare_editais(request: Request, data: dict, session_token: Optional[str] = Cookie(None)):
    """Diff two edital analyses.

    Body: { "analysis_id_a": "...", "analysis_id_b": "..." }
    Returns:
      {
        "concurso_a": {...}, "concurso_b": {...},
        "cargos_added":   [{...cargo B not in A}],
        "cargos_removed": [{...cargo A not in B}],
        "cargos_changed": [{ "nome":"...", "disciplinas_added":[], "disciplinas_removed":[] }],
        "cargos_unchanged": [names]
      }
    """
    auth_header = request.headers.get("Authorization")
    user = await account(request)

    aid_a = (data or {}).get("analysis_id_a")
    aid_b = (data or {}).get("analysis_id_b")
    if not aid_a or not aid_b:
        raise HTTPException(status_code=400, detail="Informe analysis_id_a e analysis_id_b.")
    if aid_a == aid_b:
        raise HTTPException(status_code=400, detail="Selecione dois editais diferentes.")

    doc_a = await analyses.get(user['user_id'],aid_a)
    doc_b = await analyses.get(user['user_id'],aid_b)
    if not doc_a or not doc_b:
        raise HTTPException(status_code=404, detail="Uma das análises não foi encontrada.")

    def _norm(s: str) -> str:
        return ' '.join(unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower().split())

    cargos_a = doc_a.get("cargos") or []
    cargos_b = doc_b.get("cargos") or []

    by_a = {_norm(c.get("nome", "")): c for c in cargos_a}
    by_b = {_norm(c.get("nome", "")): c for c in cargos_b}

    added_keys = [k for k in by_b if k not in by_a]
    removed_keys = [k for k in by_a if k not in by_b]
    common_keys = [k for k in by_a if k in by_b]

    def _disc_names(cargo: dict) -> set:
        return {(d.get("nome") or "").strip() for d in (cargo.get("disciplinas") or []) if d.get("nome")}

    changed = []
    unchanged = []
    for k in common_keys:
        da = _disc_names(by_a[k])
        db_ = _disc_names(by_b[k])
        added_d = sorted(db_ - da)
        removed_d = sorted(da - db_)
        if added_d or removed_d:
            changed.append({
                "nome": by_b[k].get("nome") or by_a[k].get("nome"),
                "disciplinas_added": added_d,
                "disciplinas_removed": removed_d,
            })
        else:
            unchanged.append(by_a[k].get("nome"))

    return {
        "concurso_a": doc_a.get("concurso") or {},
        "concurso_b": doc_b.get("concurso") or {},
        "pdf_filename_a": doc_a.get("pdf_filename"),
        "pdf_filename_b": doc_b.get("pdf_filename"),
        "cargos_added":   [by_b[k] for k in added_keys],
        "cargos_removed": [by_a[k] for k in removed_keys],
        "cargos_changed": changed,
        "cargos_unchanged": unchanged,
        "summary": {
            "total_a": len(cargos_a),
            "total_b": len(cargos_b),
            "added":   len(added_keys),
            "removed": len(removed_keys),
            "changed": len(changed),
            "unchanged": len(unchanged),
        },
    }
