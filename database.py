import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


def testar_conexao():
    try:
        with engine.connect() as conexao:
            resultado = conexao.execute(
                text("SELECT current_database(), current_user;")
            ).one()

            print("Conexão realizada com sucesso!")
            print(f"Database: {resultado[0]}")
            print(f"Usuário: {resultado[1]}")

    except Exception as erro:
        print("Erro ao conectar ao PostgreSQL:")
        print(erro)


if __name__ == "__main__":
    testar_conexao()