import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Carrega o .env a partir da raiz do projeto (considerando que este arquivo está em src/vizu_infra/database)
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi definida no arquivo .env")

# Cria o "motor" que será usado em toda a aplicação
engine = create_engine(DATABASE_URL)

# Cria a fábrica de sessões que será usada para interagir com o banco
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

print("Motor do banco de dados e fábrica de sessões criados com sucesso.")