import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


load_dotenv()


APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD_HASH = os.getenv("APP_PASSWORD_HASH")
JWT_SECRET = os.getenv("JWT_SECRET")

ALGORITHM = "HS256"

security = HTTPBearer(auto_error=False)


class LoginEntrada(BaseModel):
    usuario: str
    senha: str


def autenticar_usuario(usuario: str, senha: str):

    if not APP_USERNAME or not APP_PASSWORD_HASH:
        raise HTTPException(
            status_code=500,
            detail="Autenticação não configurada."
        )

    if usuario != APP_USERNAME:
        return False

    return bcrypt.checkpw(
        senha.encode("utf-8"),
        APP_PASSWORD_HASH.encode("utf-8")
    )


def criar_token(usuario: str):

    if not JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="JWT não configurado."
        )

    agora = datetime.now(timezone.utc)

    payload = {
        "sub": usuario,
        "iat": agora,
        "exp": agora + timedelta(hours=24)
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=ALGORITHM
    )


def exigir_autenticacao(
    credenciais: HTTPAuthorizationCredentials = Depends(security)
):

    if not credenciais:
        raise HTTPException(
            status_code=401,
            detail="Não autenticado."
        )

    try:

        payload = jwt.decode(
            credenciais.credentials,
            JWT_SECRET,
            algorithms=[ALGORITHM]
        )

        usuario = payload.get("sub")

        if usuario != APP_USERNAME:
            raise HTTPException(
                status_code=401,
                detail="Token inválido."
            )

        return usuario

    except jwt.ExpiredSignatureError:

        raise HTTPException(
            status_code=401,
            detail="Sessão expirada."
        )

    except jwt.InvalidTokenError:

        raise HTTPException(
            status_code=401,
            detail="Token inválido."
        )