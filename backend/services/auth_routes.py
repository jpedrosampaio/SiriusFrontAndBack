from fastapi import APIRouter, Cookie, Request, Response, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from services.auth import AuthService

router = APIRouter(prefix='/auth')
service = AuthService()


class Register(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=72)
    gemini_api_key: str | None = None


class Login(BaseModel):
    email: str
    password: str


def session_cookie(response, token):
    response.set_cookie('session_token', token, httponly=True, secure=True,
                        samesite='none', path='/', max_age=7*24*60*60)


@router.post('/register')
async def register(body: Register, response: Response):
    result = await service.register(**body.model_dump())
    session_cookie(response, result['session_token'])
    return result


@router.post('/login')
async def login(body: Login, response: Response):
    result = await service.login(**body.model_dump())
    session_cookie(response, result['session_token'])
    return result


@router.get('/me')
async def me(request: Request, session_token: str | None = Cookie(None)):
    return await service.current_user(authorization=request.headers.get('Authorization'), session_token=session_token)


@router.post('/logout')
async def logout(request: Request, response: Response, session_token: str | None = Cookie(None)):
    result = await service.logout(authorization=request.headers.get('Authorization'), session_token=session_token)
    response.delete_cookie('session_token', path='/', secure=True, httponly=True, samesite='none')
    return result


@router.get('/google-session')
async def google_session(session_id: str,response: Response):
    result = await service.google_session(session_id)
    session_cookie(response,result['session_token'])
    return result


async def account(request):
    return await service.current_user(authorization=request.headers.get('Authorization'),session_token=request.cookies.get('session_token'))


@router.patch('/profile')
async def update_profile(request: Request,body: dict):
    user = await account(request)
    return await service.update_profile(user['user_id'],body)


@router.post('/upload-picture')
async def upload_picture(request: Request,file: UploadFile = File(...)):
    await account(request)
    # A Render filesystem is not durable. Do not return a fake persisted URL.
    raise HTTPException(503,'Armazenamento de imagens ainda não configurado. O perfil continua disponível.')


@router.delete('/remove-picture')
async def remove_picture(request: Request):
    user = await account(request)
    return await service.remove_picture(user['user_id'])


@router.get('/birthday-check')
async def birthday(request: Request):
    from datetime import date
    from services.time import local_today
    user = await account(request)
    if not user.get('birth_date'): return {'is_birthday':False,'age':None}
    born = date.fromisoformat(user['birth_date'])
    today = local_today(user['timezone'])
    return {'is_birthday':(born.month,born.day)==(today.month,today.day),
        'age':today.year-born.year-((today.month,today.day)<(born.month,born.day)), 'birth_date':born.isoformat()}
