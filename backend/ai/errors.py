"""Allowlisted public failures: never interpolate provider bodies or exception text."""
import logging
import uuid
from fastapi import HTTPException

FAILURES = {
    'quota': (429, 'A cota de IA foi atingida. Confira os limites da sua conta e tente novamente quando estiver disponível.'),
    'rate_limit': (429, 'O limite de requisições da IA foi atingido. Aguarde um pouco e tente novamente.'),
    'invalid_key': (400, 'A chave de IA é inválida ou foi revogada. Confira a configuração do provedor.'),
    'permission_denied': (403, 'A conta de IA não possui acesso a este recurso. Confira as permissões do provedor.'),
    'model_unavailable': (503, 'O modelo de IA está indisponível para esta solicitação. Tente novamente mais tarde.'),
    'timeout': (504, 'O tempo de análise da IA foi excedido. Tente novamente; seus dados foram preservados.'),
    'network_error': (503, 'Não foi possível conectar ao serviço de IA. Tente novamente mais tarde.'),
    'unavailable': (503, 'O serviço de IA está temporariamente indisponível. Tente novamente mais tarde.'),
    'output_truncated': (502, 'A resposta da IA ficou incompleta. Nenhum resultado parcial foi salvo. Tente novamente.'),
    'empty_output': (502, 'A IA não retornou conteúdo. Tente novamente; seus dados foram preservados.'),
    'malformed_output': (502, 'A IA retornou uma resposta inválida ou incompleta. Nenhum resultado parcial foi salvo.'),
    'blocked_output': (422, 'A IA não pôde concluir esta solicitação devido aos filtros do provedor. Revise o pedido.'),
    'invalid_request': (502, 'O provedor não aceitou o formato da solicitação de IA. Tente novamente ou informe a referência do erro.'),
    'provider_error': (502, 'Não foi possível concluir a solicitação de IA. Tente novamente.'),
}
ALIASES = {'invalid': 'invalid_key', 'empty': 'empty_output', 'other': 'provider_error'}


def public_ai_error(kind):
    kind = ALIASES.get(kind, kind)
    kind = kind if kind in FAILURES else 'provider_error'
    status, message = FAILURES[kind]
    reference = uuid.uuid4().hex[:12]
    logging.warning('ai_request_failed kind=%s reference=%s', kind, reference)
    return HTTPException(status, {'code': 'ai_' + kind, 'message': message, 'reference': reference})


def safe_ai_message(detail):
    if not isinstance(detail, dict):
        return None
    kind = str(detail.get('code', '')).removeprefix('ai_')
    # Rebuild from constants; never trust arbitrary text in an HTTPException.
    return FAILURES[kind][1] if kind in FAILURES else None
