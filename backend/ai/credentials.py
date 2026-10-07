"""Per-account credentials. Never serialize secrets into profile responses."""
import os
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

PROVIDERS = ('gemini', 'groq')


def cipher():
    value = os.getenv('AI_KEY_ENCRYPTION_KEY', '')
    if not value:
        return None
    try:
        return Fernet(value.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, 'Configuração de criptografia da IA inválida.') from None


def credential_fields(provider, value):
    if provider not in PROVIDERS or not isinstance(value, str) or len(value) > 512:
        raise HTTPException(422, 'Provedor ou chave inválidos.')
    value = value.strip()
    prefix = f'{provider}_api_key'
    if not value:
        return {prefix: None, prefix + '_encrypted': None, prefix + '_last4': None}
    encryption = cipher()
    if not encryption:
        raise HTTPException(503, 'Configure AI_KEY_ENCRYPTION_KEY no servidor para salvar chaves com segurança. As chaves existentes continuam disponíveis.')
    return {prefix: None, prefix + '_encrypted': encryption.encrypt(value.encode()).decode(), prefix + '_last4': value[-4:]}


def public_profile(document):
    result = {k: v for k, v in document.items() if k not in ('_id', 'password') and 'api_key' not in k}
    for provider in PROVIDERS:
        prefix = f'{provider}_api_key'
        legacy = document.get(prefix) or ''
        result[f'has_{provider}_key'] = bool(legacy or document.get(prefix + '_encrypted'))
        result[f'{provider}_key_last4'] = document.get(prefix + '_last4') or legacy[-4:] or None
    return result


class Credentials:
    async def get(self, user_id):
        from uuid import UUID
        from db.session import unit_of_work
        from db.repositories.identity import IdentityRepository
        async with unit_of_work() as session:
            user = await IdentityRepository(session).by_id(UUID(str(user_id)))
            document = user.credentials if user else {}
        result = {}
        for provider in PROVIDERS:
            prefix = f'{provider}_api_key'
            encrypted = document.get(prefix + '_encrypted')
            if encrypted:
                encryption = cipher()
                if encryption:
                    try:
                        result[provider] = encryption.decrypt(encrypted.encode()).decode()
                    except (InvalidToken, ValueError, UnicodeError):
                        pass  # Key rotation requires re-entry; never expose ciphertext/errors.
        return result

    async def save(self, user_id, provider, value):
        from uuid import UUID
        from db.session import unit_of_work
        from db.repositories.identity import IdentityRepository
        from services.auth import public_user
        values = credential_fields(provider,value)
        async with unit_of_work() as session:
            user = await IdentityRepository(session).by_id(UUID(str(user_id)),lock=True)
            if user is None: raise HTTPException(404,'User not found')
            user.credentials = {**user.credentials,**values}
            await session.flush()
            return public_user(user)
