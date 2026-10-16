"""Passive allowlisted diagnostics; never tests a key or copies provider text."""
from ai.errors import FAILURES

MESSAGES={
    'analysis_provider_budget':'O orçamento de chamadas desta análise terminou. Confira os lotes antes de ampliar o limite.',
    'initial_document_budget_exceeded':'A descoberta requer mais lotes do que o orçamento inicial. Confira o tamanho antes de ampliar o limite.',
    'planned_units_exceed_remaining_budget':'As próximas etapas excedem o orçamento restante. Os lotes válidos continuam salvos.',
    'section_associations_require_review':'Existem seções com associação ambígua ao cargo. Confira suas fontes e registre a associação correta.',
    'selected_program_not_identified':'O conteúdo deste cargo não foi identificado. Confira as seções e suas associações antes de reanalisar.',
    'role_inventory_not_identified':'Nenhum cargo foi identificado com evidência. Confira a qualidade do texto e as seções do documento.',
    'requires_selective_ocr_unavailable':'Há páginas sem texto que requerem OCR. O OCR seletivo não está disponível neste ambiente.',
    'empty_text_document':'O documento não possui texto suficiente para a análise. Confira a extração local ou envie outra cópia.',
    'evidence_invalid':'Um lote não sustentou suas propostas nas fontes. Confira a seção e solicite reanálise se necessário.',
    'input_limit':'Um lote excedeu o limite de entrada. O resultado desse lote não foi confirmado.',
    'worker_interrupted':'O worker foi interrompido. Apenas o lote pendente poderá ser retomado após sua lease.',
    'unit_retry_limit':'Um lote atingiu o limite de tentativas. Confira sua seção e solicite reanálise explícita.',
    'worker_restart_retry_limit':'Um lote foi interrompido repetidamente e atingiu o limite de tentativas. Confira sua seção.',
    'analysis_checkpoint_limit':'O limite de checkpoints foi atingido. Os dados anteriores foram preservados; confira o documento.',
    'leaf_unit_limit':'O limite de subdivisões foi atingido. Confira o tamanho e a estrutura da seção.',
    'document_operational_unit_limit':'O documento excede os limites de lotes desta análise. Nenhuma chamada de IA foi iniciada.',
    'verification_findings_require_review':'A comparação com as fontes encontrou pendências no conteúdo. Confira os apontamentos.',
    'inventory_findings_require_review':'A comparação com as fontes encontrou pendências na descoberta. Confira os apontamentos.',
    'program_issues_require_review':'A consolidação identificou pendências. Confira as evidências antes de confirmar.',
    'internal_error':'Um lote não pôde ser confirmado. Use a referência de diagnóstico; os checkpoints válidos continuam salvos.',
}


def message(kind):
    if not kind:return None
    if kind in FAILURES:return FAILURES[kind][1].replace('Nenhum resultado parcial foi salvo.',
        'Este lote não foi confirmado; os checkpoints válidos foram preservados.')
    return MESSAGES.get(kind,'O processamento requer conferência. Os checkpoints válidos foram preservados.')
