import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer
)
from sqlalchemy import text

from database import engine


load_dotenv()


# =========================================================
# CONFIGURAÇÕES
# =========================================================

JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

security = HTTPBearer(auto_error=False)


# =========================================================
# BUSCAR USUÁRIO NO BANCO
# =========================================================

def buscar_usuario(usuario: str):

    query = text("""
        SELECT
            id,
            usuario,
            senha_hash,
            ativo
        FROM usuarios
        WHERE usuario = :usuario;
    """)

    with engine.connect() as conexao:

        resultado = conexao.execute(
            query,
            {
                "usuario": usuario
            }
        ).mappings().first()

    return resultado


# =========================================================
# AUTENTICAR USUÁRIO
# =========================================================

def autenticar_usuario(
    usuario: str,
    senha: str
):

    usuario_banco = buscar_usuario(usuario)

    if usuario_banco is None:
        return False

    if not usuario_banco["ativo"]:
        return False

    senha_valida = bcrypt.checkpw(
        senha.encode("utf-8"),
        usuario_banco["senha_hash"].encode("utf-8")
    )

    return senha_valida


# =========================================================
# CRIAR TOKEN JWT
# =========================================================

def criar_token(usuario: str):

    if not JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="JWT não configurado."
        )

    usuario_banco = buscar_usuario(usuario)

    if (
        usuario_banco is None
        or not usuario_banco["ativo"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Usuário inválido."
        )

    agora = datetime.now(timezone.utc)

    payload = {
        "sub": usuario_banco["usuario"],
        "user_id": usuario_banco["id"],
        "iat": agora,
        "exp": agora + timedelta(hours=24)
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=ALGORITHM
    )


# =========================================================
# VALIDAR TOKEN
# =========================================================

def exigir_autenticacao(
    credenciais: HTTPAuthorizationCredentials = Depends(security)
):

    if not credenciais:
        raise HTTPException(
            status_code=401,
            detail="Não autenticado."
        )

    if not JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="JWT não configurado."
        )

    try:

        payload = jwt.decode(
            credenciais.credentials,
            JWT_SECRET,
            algorithms=[ALGORITHM]
        )

        usuario = payload.get("sub")
        usuario_id = payload.get("user_id")

        if not usuario or not usuario_id:
            raise HTTPException(
                status_code=401,
                detail="Token inválido."
            )

        query = text("""
            SELECT
                id,
                usuario,
                ativo
            FROM usuarios
            WHERE
                id = :usuario_id
                AND usuario = :usuario;
        """)

        with engine.connect() as conexao:

            usuario_banco = conexao.execute(
                query,
                {
                    "usuario_id": usuario_id,
                    "usuario": usuario
                }
            ).mappings().first()

        if (
            usuario_banco is None
            or not usuario_banco["ativo"]
        ):
            raise HTTPException(
                status_code=401,
                detail="Usuário inválido ou inativo."
            )

        return {
            "id": usuario_banco["id"],
            "usuario": usuario_banco["usuario"]
        }

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