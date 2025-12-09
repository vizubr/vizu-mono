# services/migration_runner/main.py
from alembic.config import main as alembic_main
import os

def run_migrations():
    """Executa as migrações do Alembic de forma programática."""
    print("INFO: Iniciando migrações do banco de dados...")
    try:
        # Localiza um arquivo alembic.ini se ele existir dentro do pacote vizu_db_connector
        alembic_cfg = None
        try:
            import vizu_db_connector
            pkg_dir = os.path.dirname(vizu_db_connector.__file__)
            candidate = os.path.normpath(os.path.join(pkg_dir, '..', 'alembic.ini'))
            if os.path.exists(candidate):
                alembic_cfg = candidate
        except Exception:
            alembic_cfg = None

        # fallback para cwd
        if alembic_cfg is None and os.path.exists('alembic.ini'):
            alembic_cfg = os.path.abspath('alembic.ini')

        if alembic_cfg is None:
            raise RuntimeError('Não foi possível localizar alembic.ini (procure em libs/vizu_db_connector/alembic.ini)')

        print(f"INFO: Using alembic config: {alembic_cfg}")
        # Work in the directory that contains the alembic.ini so relative paths
        # such as 'alembic/script.py.mako' are resolved correctly.
        alembic_dir = os.path.dirname(alembic_cfg)
        print(f"INFO: Changing working directory to alembic dir: {alembic_dir}")
        os.chdir(alembic_dir)

        # IMPORTANT: Do NOT autogenerate revisions inside the container in CI/production.
        # The correct workflow is to generate revision files locally (or in a CI job),
        # commit them to the repo under `libs/vizu_db_connector/alembic/versions/` and
        # then have the runner apply `upgrade head` here. Autogenerating at runtime
        # causes non-deterministic revisions and can fail when templates or imports
        # differ between environments.
        print("INFO: Upgrading to heads...")
        alembic_main(["--config", alembic_cfg, "upgrade", "heads"])
        print("SUCESSO: Migrações concluídas.")
    except Exception as e:
        print(f"ERRO: Falha ao executar migrações do Alembic: {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    run_migrations()
