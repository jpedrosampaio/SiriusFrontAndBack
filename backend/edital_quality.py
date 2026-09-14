"""Shared guards for edital extraction, repair, cache and import."""
import re
import unicodedata


def normalized_name(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c)).casefold()
    value = re.sub(r"^[a-z]\d{2}\s*[-–—:]?\s*", "", value)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def generic_discipline(discipline):
    name = normalized_name(discipline.get("nome") if isinstance(discipline, dict) else discipline)
    return bool(re.match(r"^(?:(?:prova|provas) (?:objetiva|objetivas) )?(?:conhecimentos|disciplinas) (?:gerais|especificos|basicos|complementares)(?: |$)", name))


def needs_disciplines(cargo):
    disciplines = cargo.get("disciplinas") or []
    return not disciplines or any(
        not isinstance(d, dict) or not d.get("nome") or generic_discipline(d)
        or not (d.get("conteudo_programatico") or d.get("topicos"))
        for d in disciplines
    )


def edital_context(text, cargo_names=()):
    """Keep the complete document, including late syllabus annexes, or fail explicitly.

    600k characters comfortably includes the 246k-character TJCE regression document.
    Do not label an arbitrary prefix as the complete edital.
    """
    text = text or ""
    if len(text) > 600_000:
        raise ValueError("O edital excede o limite de texto para análise completa. Envie um PDF com o quadro de cargos, as regras das provas e o conteúdo programático completo.")
    if not cargo_names:
        return text
    # Recognize explicitly delimited, coded role sections. Fall back to the full
    # document when boundaries or exact role matches are ambiguous.
    lines = list(re.finditer(r"(?m)^.*$", text))
    start = next((m.start() for m in lines if normalized_name(m.group()) in ("conteudo programatico", "conteudos programaticos")), None)
    if start is None:
        return text
    headings = [m for m in lines if m.start() > start and re.match(r"\s*[A-Za-z]\d{2}\s*[-–—]\s*\S", m.group())]
    if not headings:
        return text
    sections = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        annex = re.search(r"(?m)^\s*ANEXO\s+[IVX\d]+\s*$", text[heading.end():end])
        if annex:
            end = heading.end() + annex.start()
        name = normalized_name(heading.group())
        if name in sections:
            return text
        sections[name] = text[heading.start():end]
    requested = [normalized_name(name) for name in cargo_names]
    if not all(name in sections for name in requested):
        return text
    return (text[:start] + "\n\nCONTEÚDO PROGRAMÁTICO COMUM:\n"
            + text[start:headings[0].start()] + "\n\nSEÇÕES DOS CARGOS SOLICITADOS:\n"
            + "\n\n".join(sections[name] for name in requested))


def mark_discipline_quality(cargos):
    for cargo in cargos:
        incomplete = needs_disciplines(cargo)
        cargo["disciplinas_status"] = "incompleto" if incomplete else "extraido"
        cargo["disciplinas_aviso"] = (
            "Não foi possível identificar todas as disciplinas deste cargo. Reanalise o edital antes de criar o programa."
            if incomplete else ""
        )
    return cargos
