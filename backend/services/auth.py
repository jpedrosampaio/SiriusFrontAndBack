import asyncio
import secrets
from uuid import UUID
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work


def public_user(user):
    data = {'user_id': str(user.id), 'email': user.email, 'name': user.name, 'picture': user.picture,
        'xp': user.xp, 'rank': user.rank, 'bio': user.bio, 'birth_date': user.preferences.get('birth_date'),
        'timezone': user.timezone, 'created_at': user.created_at,
        'health_condition': user.preferences.get('health_condition')}
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
    async def profile(self, user_id):
        async with unit_of_work() as session:
            user = await IdentityRepository(session).by_id(UUID(str(user_id)))
            if user is None:
                raise HTTPException(404, 'User not found')
            return public_user(user)

    async def update_profile(self, user_id, values):
        async with unit_of_work() as session:
            user = await IdentityRepository(session).by_id(UUID(str(user_id)), lock=True)
            if user is None:
                raise HTTPException(404, 'User not found')
            allowed = {'name','bio','birth_date','health_condition','gemini_api_key','timezone'}
            if not allowed.intersection(values):
                raise HTTPException(400, 'Nenhum campo para atualizar')
            for key in ('name','bio'):
                if key in values:
                    if not isinstance(values[key], str) or len(values[key]) > (200 if key == 'name' else 5000):
                        raise HTTPException(422, 'Perfil inválido')
                    setattr(user,key,values[key])
            preferences = dict(user.preferences)
            for key in ('birth_date','health_condition'):
                if key in values:
                    value = values[key]
                    if value is not None and (not isinstance(value,str) or len(value)>5000):
                        raise HTTPException(422, 'Perfil inválido')
                    if key == 'birth_date' and value:
                        from datetime import date
                        try: date.fromisoformat(value)
                        except ValueError: raise HTTPException(422,'Data de nascimento inválida') from None
                    preferences[key] = value
            user.preferences = preferences
            if 'timezone' in values:
                from services.time import validate_timezone
                try: user.timezone = validate_timezone(values['timezone'])
                except ValueError: raise HTTPException(422,'Fuso horário inválido') from None
            if 'gemini_api_key' in values:
                from ai.credentials import credential_fields
                user.credentials = {**user.credentials,**credential_fields('gemini',values['gemini_api_key'] or '')}
            await session.flush()
            return public_user(user)

    async def remove_picture(self,user_id):
        async with unit_of_work() as session:
            user = await IdentityRepository(session).by_id(UUID(str(user_id)),lock=True)
            if user is None: raise HTTPException(404,'User not found')
            user.picture = None
        return {'message':'Profile picture removed'}

    async def google_session(self,session_id):
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.get('https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data',headers={'X-Session-ID':session_id})
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError,ValueError):
                raise HTTPException(400,'Invalid session ID') from None
        if not all(isinstance(data.get(k),str) and data[k] for k in ('email','name','session_token')):
            raise HTTPException(400,'Invalid session ID')
        async with unit_of_work() as session:
            repo = IdentityRepository(session)
            user = await repo.by_email(data['email'])
            if user is None:
                user = await repo.create(email=data['email'],name=data['name'],password_hash=None)
                user.picture = data.get('picture')
            token = 'session_'+secrets.token_urlsafe(32)
            await repo.add_session(user.id,token,datetime.now(timezone.utc)+timedelta(days=7))
            return {'session_token':token,'user':public_user(user)}

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
