from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from .models import FonteDeDados
import uuid



# Carrega as variáveis de ambiente para pegar a string de conexão do banco
load_dotenv()

from .models import Base, ClienteVizu, ConfiguracaoNegocio




# --- Configuração da Conexão com o Banco de Dados ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://vizu_user:vizu_password@localhost:5432/vizu_infra_dev")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    """Função para obter uma sessão de banco de dados."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Funções do Repositório ---
def get_cliente_por_api_key(db_session, api_key: str) -> ClienteVizu | None:
    """Busca um cliente pela sua chave de API."""
    return db_session.query(ClienteVizu).filter(ClienteVizu.api_key == api_key).first()

def criar_cliente_completo(db_session, nome: str, api_key: str, tier: str, tipo: str) -> ClienteVizu:
    """
    Cria um novo ClienteVizu e sua ConfiguracaoNegocio associada em uma única transação.
    """
    # Cria o objeto do novo cliente
    novo_cliente = ClienteVizu(
        nome_empresa=nome,
        api_key=api_key,
        tier=tier,
        tipo_cliente=tipo
    )

    # Cria a configuração padrão para este cliente
    configuracao_padrao = ConfiguracaoNegocio()
    novo_cliente.configuracoes = configuracao_padrao # Associa a configuração ao cliente

    # Adiciona à sessão e commita no banco de dados
    db_session.add(novo_cliente)
    db_session.commit()
    db_session.refresh(novo_cliente) # Atualiza o objeto com os dados do banco (como o ID)

    return novo_cliente


def criar_fonte_de_dados(db_session, cliente_id: uuid.UUID, tipo: str, uri: str) -> FonteDeDados:
    """Cria um novo registro de FonteDeDados no banco."""
    nova_fonte = FonteDeDados(
        cliente_vizu_id=cliente_id,
        tipo_fonte=tipo,
        uri=uri
    )
    db_session.add(nova_fonte)
    db_session.commit()
    db_session.refresh(nova_fonte)
    return nova_fonte

