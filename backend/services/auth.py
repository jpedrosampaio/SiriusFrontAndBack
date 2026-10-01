import asyncio
import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work


def public_user(user):
    data = {'user_id': str(user.id), 'email': user.email, 'name': user.name, 'picture': user.picture,
        'xp': user.xp, 'rank': user.rank, 'bio': user.bio, 'birth_date': user.preferences.get('birth_date'),
        'timezone': user.timezone, 'created_at': user.created_at}
    for provider in ('gemini', 'groq'):
        data[f'has_{provider}_key'] = bool(user.credentials.get(f'{provider}_api_key_encrypted'))
        data[f'{provider}_key_last4'] = user.credentials.get(f'{provider}_api_key_last4')
    return data


def password_bytes(password):
    encoded = password.encode('utf-8')
    if not encoded or len(encoded) > 72:
        raise HTTPException(422, 'A senha deve conter entre 1 e 72 bytes UTF-8.')
    return encoded


class AuthService:
    async def register(self, *, email, name, password, gemini_api_key=None):
        encoded = password_bytes(password)
        hashed = await asyncio.to_thread(bcrypt.hashpw, encoded, bcrypt.gensalt())
        credentials = {}
        if gemini_api_key:
            from ai.credentials import credential_fields
            credentials = credential_fields('gemini', gemini_api_key)
        try:
            async with unit_of_work() as session:
                repo = IdentityRepository(session)
                user = await repo.create(email=email, name=name, password_hash=hashed.decode())
                user.credentials = credentials
                token = 'session_' + secrets.token_urlsafe(32)
                await repo.add_session(user.id, token, datetime.now(timezone.utc)+timedelta(days=7))
                result = {'session_token': token, 'user': public_user(user)}
            return result
        except IntegrityError as error:
            if getattr(error.orig, 'sqlstate', None) == '23505':
                raise HTTPException(400, 'Email already registered') from None
            raise

    async def login(self, *, email, password):
        encoded = password_bytes(password)
        async with unit_of_work() as session:
            repo = IdentityRepository(session)
            user = await repo.by_email(email)
            if user is None or not user.password_hash:
                raise HTTPException(401, 'Invalid credentials')
            if not await asyncio.to_thread(bcrypt.checkpw, encoded, user.password_hash.encode()):
                raise HTTPException(401, 'Invalid credentials')
            token = 'session_' + secrets.token_urlsafe(32)
            await repo.add_session(user.id, token, datetime.now(timezone.utc)+timedelta(days=7))
            return {'session_token': token, 'user': public_user(user)}

    async def current_user(self, *, authorization=None, session_token=None):
        token = self.token(authorization, session_token)
        if not token:
            raise HTTPException(401, 'Not authenticated')
        async with unit_of_work() as session:
            user = await IdentityRepository(session).authenticated(token)
            if user is None:
                raise HTTPException(401, 'Invalid session')
            return public_user(user)

    @staticmethod
    def token(authorization=None, session_token=None):
        if session_token:
            return session_token
        if authorization and authorization.startswith('Bearer '):
            return authorization[7:]
        return None

    async def logout(self, *, authorization=None, session_token=None):
        token = self.token(authorization, session_token)
        if token:
            async with unit_of_work() as session:
                await IdentityRepository(session).revoke(token)
        return {'message': 'Logged out'}
