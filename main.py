from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
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
# MODELOS
# =========================================================

class RendaEntrada(BaseModel):
    renda: Decimal = Field(ge=0)


class GastoEntrada(BaseModel):
    tipo: Literal["FIXO", "CARTAO"]
    descricao: str
    valor: Decimal = Field(ge=0)
    data_gasto: date


class GastoAtualizacao(BaseModel):
    descricao: str
    valor: Decimal = Field(ge=0)
    data_gasto: date


# =========================================================
# ROTA INICIAL
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
# CONSULTAR MÊS
# =========================================================

@app.get("/mes/{ano}/{mes}")
def consultar_mes(
    ano: int,
    mes: int,
    usuario: dict = Depends(exigir_autenticacao)
):

    if mes < 1 or mes > 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )

    usuario_id = usuario["id"]

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

        WHERE
            cm.usuario_id = :usuario_id
            AND cm.competencia = make_date(:ano, :mes, 1)

        GROUP BY
            cm.id,
            cm.competencia,
            cm.renda;
    """)

    with engine.connect() as conexao:

        resumo = conexao.execute(
            query_resumo,
            {
                "usuario_id": usuario_id,
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
                valor,
                data_gasto

            FROM gastos

            WHERE controle_mensal_id = :controle_id

            ORDER BY
                data_gasto,
                id;
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
            "valor": float(gasto["valor"]),
            "data_gasto": gasto["data_gasto"]
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
# CADASTRAR OU ALTERAR RENDA
# =========================================================

@app.put("/mes/{ano}/{mes}/renda")
def atualizar_renda(
    ano: int,
    mes: int,
    dados: RendaEntrada,
    usuario: dict = Depends(exigir_autenticacao)
):

    if mes < 1 or mes > 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )

    usuario_id = usuario["id"]

    query = text("""
        INSERT INTO controle_mensal (
            usuario_id,
            competencia,
            renda
        )
        VALUES (
            :usuario_id,
            make_date(:ano, :mes, 1),
            :renda
        )

        ON CONFLICT (
            usuario_id,
            competencia
        )

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
                "usuario_id": usuario_id,
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
    usuario: dict = Depends(exigir_autenticacao)
):

    if mes < 1 or mes > 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )

    usuario_id = usuario["id"]

    descricao = dados.descricao.strip()

    if not descricao:
        raise HTTPException(
            status_code=400,
            detail="A descrição não pode ficar vazia."
        )

    if (
        dados.data_gasto.year != ano
        or dados.data_gasto.month != mes
    ):
        raise HTTPException(
            status_code=400,
            detail="A data do gasto deve pertencer ao mês selecionado."
        )

    with engine.begin() as conexao:

        controle = conexao.execute(
            text("""
                SELECT id

                FROM controle_mensal

                WHERE
                    usuario_id = :usuario_id
                    AND competencia =
                        make_date(:ano, :mes, 1);
            """),
            {
                "usuario_id": usuario_id,
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
                    valor,
                    data_gasto
                )
                VALUES (
                    :controle_id,
                    :tipo,
                    :descricao,
                    :valor,
                    :data_gasto
                )

                RETURNING
                    id,
                    tipo,
                    descricao,
                    valor,
                    data_gasto;
            """),
            {
                "controle_id": controle["id"],
                "tipo": dados.tipo,
                "descricao": descricao,
                "valor": dados.valor,
                "data_gasto": dados.data_gasto
            }
        ).mappings().first()

    return {
        "mensagem": "Gasto adicionado com sucesso.",
        "gasto": {
            "id": resultado["id"],
            "tipo": resultado["tipo"],
            "descricao": resultado["descricao"],
            "valor": float(resultado["valor"]),
            "data_gasto": resultado["data_gasto"]
        }
    }


# =========================================================
# ALTERAR GASTO
# =========================================================

@app.put("/gastos/{gasto_id}")
def atualizar_gasto(
    gasto_id: int,
    dados: GastoAtualizacao,
    usuario: dict = Depends(exigir_autenticacao)
):

    usuario_id = usuario["id"]

    descricao = dados.descricao.strip()

    if not descricao:
        raise HTTPException(
            status_code=400,
            detail="A descrição não pode ficar vazia."
        )

    with engine.begin() as conexao:

        # Verifica se o gasto realmente pertence
        # ao usuário que está autenticado
        gasto_atual = conexao.execute(
            text("""
                SELECT
                    g.id,
                    cm.competencia

                FROM gastos g

                INNER JOIN controle_mensal cm
                    ON cm.id = g.controle_mensal_id

                WHERE
                    g.id = :gasto_id
                    AND cm.usuario_id = :usuario_id;
            """),
            {
                "gasto_id": gasto_id,
                "usuario_id": usuario_id
            }
        ).mappings().first()

        if gasto_atual is None:
            raise HTTPException(
                status_code=404,
                detail="Gasto não encontrado."
            )

        competencia = gasto_atual["competencia"]

        if (
            dados.data_gasto.year != competencia.year
            or dados.data_gasto.month != competencia.month
        ):
            raise HTTPException(
                status_code=400,
                detail="A data do gasto deve pertencer ao mês do lançamento."
            )

        resultado = conexao.execute(
            text("""
                UPDATE gastos

                SET
                    descricao = :descricao,
                    valor = :valor,
                    data_gasto = :data_gasto

                WHERE id = :gasto_id

                RETURNING
                    id,
                    tipo,
                    descricao,
                    valor,
                    data_gasto;
            """),
            {
                "gasto_id": gasto_id,
                "descricao": descricao,
                "valor": dados.valor,
                "data_gasto": dados.data_gasto
            }
        ).mappings().first()

    return {
        "mensagem": "Gasto atualizado com sucesso.",
        "gasto": {
            "id": resultado["id"],
            "tipo": resultado["tipo"],
            "descricao": resultado["descricao"],
            "valor": float(resultado["valor"]),
            "data_gasto": resultado["data_gasto"]
        }
    }


# =========================================================
# EXCLUIR GASTO
# =========================================================

@app.delete("/gastos/{gasto_id}")
def excluir_gasto(
    gasto_id: int,
    usuario: dict = Depends(exigir_autenticacao)
):

    usuario_id = usuario["id"]

    query = text("""
        DELETE FROM gastos g

        USING controle_mensal cm

        WHERE
            g.controle_mensal_id = cm.id
            AND g.id = :gasto_id
            AND cm.usuario_id = :usuario_id

        RETURNING g.id;
    """)

    with engine.begin() as conexao:

        resultado = conexao.execute(
            query,
            {
                "gasto_id": gasto_id,
                "usuario_id": usuario_id
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