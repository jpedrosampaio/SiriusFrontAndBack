import pdfplumber
from typing import Optional

def extract_structured(pdf_bytes: bytes) -> dict:
    """Retorna texto por página e tabelas extraídas separadamente."""
    pages_text = []
    tables_raw = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages_text.append({"page": i, "text": text})
            page_tables = page.extract_tables()
            for t in page_tables:
                tables_raw.append({"page": i, "rows": t})
    full_text = "\n".join(p["text"] for p in pages_text)
    return {"pages": pages_text, "tables": tables_raw, "full_text": full_text}


_VAGAS_KEYWORDS = ["cargo", "vaga", "remuneraç", "escolaridade", "perfil", "especialidade",
                   "quantidade", "vagas reservadas", "cadastro reserva"]


def extract_quadro_vagas(tables: list[dict]) -> list[dict]:
    """Heurística: tabela com colunas tipo cargo/vagas/remuneração/escolaridade.
    Detecta pelo cabeçalho (primeira linha) contendo palavras-chave."""
    resultado = []
    for t in tables:
        header = [str(c).lower().strip() if c else "" for c in t["rows"][0]]
        match_count = sum(any(k in h for k in _VAGAS_KEYWORDS) for h in header)
        if match_count >= 2:
            resultado.append(t)
    return resultado


def extract_text(pdf_bytes: bytes) -> str:
    """Wrapper rápido — só texto puro. Usado nos lugares que ainda esperam string."""
    return extract_structured(pdf_bytes)["full_text"]
