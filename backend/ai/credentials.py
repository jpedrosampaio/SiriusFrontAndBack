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
    def __init__(self, db):
        self.db = db

    async def get(self, user_id):
        document = await self.db.users.find_one({'user_id': user_id}) or {}
        result = {}
        for provider in PROVIDERS:
            prefix = f'{provider}_api_key'
            encrypted, legacy = document.get(prefix + '_encrypted'), document.get(prefix)
            if encrypted:
                encryption = cipher()
                if encryption:
                    try:
                        result[provider] = encryption.decrypt(encrypted.encode()).decode()
                    except (InvalidToken, ValueError, UnicodeError):
                        pass  # Key rotation requires re-entry; never expose ciphertext/errors.
            elif legacy:
                result[provider] = legacy
                if cipher():
                    # Compare-and-set prevents migration from overwriting a concurrent edit.
                    await self.db.users.update_one({'user_id': user_id, prefix: legacy}, {'$set': credential_fields(provider, legacy)})
        return result

    async def save(self, user_id, provider, value):
        await self.db.users.update_one({'user_id': user_id}, {'$set': credential_fields(provider, value)})
        return public_profile(await self.db.users.find_one({'user_id': user_id}) or {})
