import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


load_dotenv()


database_url = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)


engine = create_engine(
    database_url,
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