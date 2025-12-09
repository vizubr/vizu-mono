# libs/vizu_db_connector/src/vizu_db_connector/operations.py

from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from typing import Dict, Any, Generator, Tuple
from contextlib import contextmanager
import uuid

# Importa a fábrica de sessões do setup de DB
from .database import SessionLocal

# Importa o modelo ORM que será usado para salvar e buscar
from vizu_models import CredencialServicoExterno


class VizuDBConnector:
    """
    Classe de operações de alto nível para persistência e recuperação de dados.
    Encapsula o ORM para que os serviços não interajam diretamente com Sessions.
    """

    def __init__(self, SessionLocal: callable = SessionLocal):
        # Injeção de dependência para Testabilidade
        self.SessionLocal = SessionLocal

    @contextmanager
    def _get_db(self) -> Generator[Session, None, None]:
        """Gerenciador de contexto de sessão interno."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # --- MÉTODOS REQUERIDOS PELA DATA_INGESTION_API (Transacional) ---
    async def save_credential_reference(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Salva a referência da credencial (Secret ID) no DB (PostgreSQL).
        Transacional: Garante commit ou rollback da operação.
        """
        with self._get_db() as db:
            try:
                novo_registro = CredencialServicoExterno(
                    cliente_vizu_id=data["cliente_vizu_id"],
                    nome_servico=data["nome_conexao"],
                    # O Secret ID é o campo que armazena a referência para o Secret Manager
                    credenciais_cifradas=data["secret_manager_id"],
                )
                db.add(novo_registro)
                db.commit()
                # Garante que o ID gerado pelo DB esteja disponível para retorno
                db.refresh(novo_registro)
                # Retorna os metadados com o ID real do DB
                return {**data, "id_credencial": str(novo_registro.id)}
            except Exception as e:
                db.rollback()
                raise e

    # --- MÉTODOS REQUERIDOS PELO DATA_PROCESSING WORKER ---
    async def get_secret_manager_id_and_type(
        self, id_credencial: str
    ) -> Tuple[str, str]:
        """
        Busca o Secret ID (referência) e o tipo de serviço (ex: GOOGLE_ADS) para o Worker.
        """
        with self._get_db() as db:
            try:
                # Converte a string UUID para o tipo UUID se necessário (depende da coluna ORM)
                credencial_uuid = uuid.UUID(id_credencial)

                registro = (
                    db.query(CredencialServicoExterno)
                    .filter(CredencialServicoExterno.id == credencial_uuid)
                    .one()
                )

                # credenciais_cifradas armazena o Secret Manager ID
                # nome_servico armazena o tipo de conexão
                return (
                    registro.credenciais_cifradas,
                    registro.nome_servico.value,
                )  # Assumindo que nome_servico é um Enum e precisa de .value
            except NoResultFound:
                # Erro claro para o Worker saber que a credencial não existe
                raise ValueError(
                    f"Credencial não encontrada para o ID: {id_credencial}"
                )
            except ValueError:
                # Erro se o ID não for um UUID válido
                raise ValueError(
                    f"O ID fornecido não é um UUID válido: {id_credencial}"
                )

    # --- Conversas / Mensagens ---
    async def create_or_get_conversa(
        self, session_id: str | None, cliente_final_id: int | None = None,
        cliente_vizu_id: str | None = None
    ) -> str:
        """
        Cria uma conversa (ou retorna a existente) mapeada pelo `session_id`.
        Retorna o UUID da conversa (como string).

        Args:
            session_id: Identificador da sessão
            cliente_final_id: ID do cliente final (opcional)
            cliente_vizu_id: ID do cliente Vizu (obrigatório para RLS)
        """
        with self._get_db() as db:
            from vizu_models import Conversa
            import uuid

            if session_id:
                existente = (
                    db.query(Conversa).filter(Conversa.session_id == session_id).first()
                )
                if existente:
                    return str(existente.id)

            # Parse UUID if provided as string
            cid = None
            if cliente_vizu_id:
                try:
                    cid = uuid.UUID(cliente_vizu_id) if isinstance(cliente_vizu_id, str) else cliente_vizu_id
                except Exception:
                    raise ValueError(f"cliente_vizu_id inválido: {cliente_vizu_id}")

            nova = Conversa(
                session_id=session_id,
                cliente_final_id=cliente_final_id,
                cliente_vizu_id=cid
            )
            db.add(nova)
            db.commit()
            db.refresh(nova)
            return str(nova.id)

    async def add_mensagem(
        self, conversa_id: str, remetente: str, conteudo: str
    ) -> int:
        """
        Adiciona uma mensagem a uma conversa. Retorna o ID numérico da mensagem.
        remetente: 'user' ou 'ai' (lowercase)
        """
        with self._get_db() as db:
            from vizu_models import Mensagem, Remetente
            import uuid

            try:
                cid = uuid.UUID(conversa_id)
            except Exception:
                raise ValueError("conversa_id inválido")

            # Map the string to the enum (ensure lowercase)
            remetente_lower = remetente.lower()
            if remetente_lower == "user":
                remetente_enum = Remetente.USER
            elif remetente_lower == "ai":
                remetente_enum = Remetente.AI
            else:
                raise ValueError(f"remetente inválido: {remetente}")

            # Pass the enum object itself; SQLModel/SQLAlchemy will use .value for DB
            msg = Mensagem(conversa_id=cid, remetente=remetente_enum, conteudo=conteudo)
            db.add(msg)
            db.commit()
            db.refresh(msg)
            return int(msg.id)

    async def insert_dataframe(self, df: Any, table_name: str, **kwargs):
        """
        Salva o DataFrame transformado (Carga - L do ELT) no PostgreSQL.
        Modularização/Agnosticismo: Recebe o nome da tabela como parâmetro, não hardcodeado.
        """
        # A carga real de um DataFrame deve usar o Engine diretamente
        # para otimizar a operação de I/O em massa.
        db_session = self.SessionLocal()
        try:
            engine = db_session.get_bind()  # Obtém o Engine vinculado à sessão
            # Import pandas lazily to avoid requiring it at module import time
            # for runtime environments that don't need DataFrame features.
            try:
                pass
            except Exception as e:
                raise RuntimeError(
                    "pandas is required for insert_dataframe but is not installed"
                ) from e

            df.to_sql(
                name=table_name,
                con=engine,
                if_exists="append",
                index=False,
                **kwargs,  # Permite passar parâmetros adicionais do pandas.to_sql (ex: dtype mapping)
            )
        finally:
            db_session.close()
