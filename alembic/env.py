from logging.config import fileConfig
from alembic import context

# Importa a Base dos nossos modelos e a 'engine' da nossa conexão centralizada.
# Graças à configuração 'python_package_dir' no alembic.ini, o Alembic
# agora sabe como encontrar o pacote 'vizu_infra' dentro de 'src/'.
from vizu_infra.database.models import Base
from vizu_infra.database.connection import engine

# --- A partir daqui, a configuração padrão do Alembic ---

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Define o target_metadata para que o 'autogenerate' encontre nossas tabelas
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Roda as migrações em modo 'offline'."""
    url = engine.url # Usa a URL da nossa engine centralizada
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Roda as migrações em modo 'online'."""
    # Usa a nossa 'engine' centralizada diretamente
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()