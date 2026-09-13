from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import engine

from auth import (
    LoginEntrada,
    autenticar_usuario,
    criar_token,
    exigir_autenticacao
)


# =========================================================
# CRIAÇÃO DA API
# =========================================================

app = FastAPI(
    title="API Controle de Gastos",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# MODELOS DE DADOS
# =========================================================

class RendaEntrada(BaseModel):
    renda: Decimal = Field(ge=0)


class GastoEntrada(BaseModel):
    tipo: Literal["FIXO", "CARTAO"]
    descricao: str
    valor: Decimal = Field(ge=0)


class GastoAtualizacao(BaseModel):
    descricao: str
    valor: Decimal = Field(ge=0)


# =========================================================
# PÁGINA INICIAL
# =========================================================

@app.get("/")
def inicio():
    return {
        "mensagem": "API Controle de Gastos funcionando!"
    }


# =========================================================
# LOGIN
# =========================================================

@app.post("/login")
def login(dados: LoginEntrada):

    if not autenticar_usuario(
        dados.usuario,
        dados.senha
    ):
        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos."
        )

    token = criar_token(dados.usuario)

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# =========================================================
# CONSULTAR UM MÊS
# =========================================================

@app.get("/mes/{ano}/{mes}")
def consultar_mes(
    ano: int,
    mes: int,
    _usuario: str = Depends(exigir_autenticacao)
):

    if mes < 1 or mes > 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )

    query_resumo = text("""
        SELECT
            cm.id,
            cm.competencia,
            cm.renda,

            COALESCE(
                SUM(
                    CASE
                        WHEN g.tipo = 'FIXO'
                        THEN g.valor
                        ELSE 0
                    END
                ),
                0
            ) AS total_gastos_fixos,

            COALESCE(
                SUM(
                    CASE
                        WHEN g.tipo = 'CARTAO'
                        THEN g.valor
                        ELSE 0
                    END
                ),
                0
            ) AS total_cartoes,

            COALESCE(
                SUM(g.valor),
                0
            ) AS total_gastos,

            cm.renda - COALESCE(
                SUM(g.valor),
                0
            ) AS saldo_disponivel

        FROM controle_mensal cm

        LEFT JOIN gastos g
            ON g.controle_mensal_id = cm.id

        WHERE cm.competencia = make_date(:ano, :mes, 1)

        GROUP BY
            cm.id,
            cm.competencia,
            cm.renda;
    """)

    with engine.connect() as conexao:

        resumo = conexao.execute(
            query_resumo,
            {
                "ano": ano,
                "mes": mes
            }
        ).mappings().first()

        if resumo is None:
            raise HTTPException(
                status_code=404,
                detail="Não existem dados cadastrados para esse mês."
            )

        query_gastos = text("""
            SELECT
                id,
                tipo,
                descricao,
                valor
            FROM gastos
            WHERE controle_mensal_id = :controle_id
            ORDER BY id;
        """)

        gastos = conexao.execute(
            query_gastos,
            {
                "controle_id": resumo["id"]
            }
        ).mappings().all()

    gastos_fixos = []
    cartoes = []

    for gasto in gastos:

        item = {
            "id": gasto["id"],
            "descricao": gasto["descricao"],
            "valor": float(gasto["valor"])
        }

        if gasto["tipo"] == "FIXO":
            gastos_fixos.append(item)

        elif gasto["tipo"] == "CARTAO":
            cartoes.append(item)

    return {
        "competencia": resumo["competencia"],
        "renda": float(resumo["renda"]),
        "total_gastos_fixos": float(
            resumo["total_gastos_fixos"]
        ),
        "total_cartoes": float(
            resumo["total_cartoes"]
        ),
        "total_gastos": float(
            resumo["total_gastos"]
        ),
        "saldo_disponivel": float(
            resumo["saldo_disponivel"]
        ),
        "gastos_fixos": gastos_fixos,
        "cartoes": cartoes
    }


# =========================================================
# CADASTRAR OU ALTERAR A RENDA DO MÊS
# =========================================================

@app.put("/mes/{ano}/{mes}/renda")
def atualizar_renda(
    ano: int,
    mes: int,
    dados: RendaEntrada,
    _usuario: str = Depends(exigir_autenticacao)
):

    if mes < 1 or mes > 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )

    query = text("""
        INSERT INTO controle_mensal (
            competencia,
            renda
        )
        VALUES (
            make_date(:ano, :mes, 1),
            :renda
        )

        ON CONFLICT (competencia)

        DO UPDATE SET
            renda = EXCLUDED.renda

        RETURNING
            id,
            competencia,
            renda;
    """)

    with engine.begin() as conexao:

        resultado = conexao.execute(
            query,
            {
                "ano": ano,
                "mes": mes,
                "renda": dados.renda
            }
        ).mappings().first()

    return {
        "mensagem": "Renda salva com sucesso.",
        "competencia": resultado["competencia"],
        "renda": float(resultado["renda"])
    }


# =========================================================
# ADICIONAR GASTO
# =========================================================

@app.post("/mes/{ano}/{mes}/gastos")
def adicionar_gasto(
    ano: int,
    mes: int,
    dados: GastoEntrada,
    _usuario: str = Depends(exigir_autenticacao)
):

    if mes < 1 or mes > 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )

    descricao = dados.descricao.strip()

    if not descricao:
        raise HTTPException(
            status_code=400,
            detail="A descrição não pode ficar vazia."
        )

    with engine.begin() as conexao:

        controle = conexao.execute(
            text("""
                SELECT id
                FROM controle_mensal
                WHERE competencia =
                    make_date(:ano, :mes, 1);
            """),
            {
                "ano": ano,
                "mes": mes
            }
        ).mappings().first()

        if controle is None:
            raise HTTPException(
                status_code=404,
                detail="Cadastre a renda desse mês primeiro."
            )

        resultado = conexao.execute(
            text("""
                INSERT INTO gastos (
                    controle_mensal_id,
                    tipo,
                    descricao,
                    valor
                )
                VALUES (
                    :controle_id,
                    :tipo,
                    :descricao,
                    :valor
                )

                RETURNING
                    id,
                    tipo,
                    descricao,
                    valor;
            """),
            {
                "controle_id": controle["id"],
                "tipo": dados.tipo,
                "descricao": descricao,
                "valor": dados.valor
            }
        ).mappings().first()

    return {
        "mensagem": "Gasto adicionado com sucesso.",
        "gasto": {
            "id": resultado["id"],
            "tipo": resultado["tipo"],
            "descricao": resultado["descricao"],
            "valor": float(resultado["valor"])
        }
    }


# =========================================================
# ALTERAR GASTO
# =========================================================

@app.put("/gastos/{gasto_id}")
def atualizar_gasto(
    gasto_id: int,
    dados: GastoAtualizacao,
    _usuario: str = Depends(exigir_autenticacao)
):

    descricao = dados.descricao.strip()

    if not descricao:
        raise HTTPException(
            status_code=400,
            detail="A descrição não pode ficar vazia."
        )

    query = text("""
        UPDATE gastos

        SET
            descricao = :descricao,
            valor = :valor

        WHERE id = :gasto_id

        RETURNING
            id,
            tipo,
            descricao,
            valor;
    """)

    with engine.begin() as conexao:

        resultado = conexao.execute(
            query,
            {
                "gasto_id": gasto_id,
                "descricao": descricao,
                "valor": dados.valor
            }
        ).mappings().first()

    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail="Gasto não encontrado."
        )

    return {
        "mensagem": "Gasto atualizado com sucesso.",
        "gasto": {
            "id": resultado["id"],
            "tipo": resultado["tipo"],
            "descricao": resultado["descricao"],
            "valor": float(resultado["valor"])
        }
    }


# =========================================================
# EXCLUIR GASTO
# =========================================================

@app.delete("/gastos/{gasto_id}")
def excluir_gasto(
    gasto_id: int,
    _usuario: str = Depends(exigir_autenticacao)
):

    query = text("""
        DELETE FROM gastos
        WHERE id = :gasto_id
        RETURNING id;
    """)

    with engine.begin() as conexao:

        resultado = conexao.execute(
            query,
            {
                "gasto_id": gasto_id
            }
        ).first()

    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail="Gasto não encontrado."
        )

    return {
        "mensagem": "Gasto excluído com sucesso."
    }