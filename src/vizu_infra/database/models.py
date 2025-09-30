import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, JSON, Text, Boolean, Integer
)
from sqlalchemy import UniqueConstraint

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Tabela 1: Nossos Clientes (PMEs e Projetos Internos)
class ClienteVizu(Base):
    __tablename__ = "clientes_vizu"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_empresa = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False, unique=True)
    tier = Column(String(50), nullable=False, default="sme")
    tipo_cliente = Column(String(50), nullable=False, default="externo")
    criado_em = Column(DateTime, default=datetime.utcnow)

    configuracoes = relationship("ConfiguracaoNegocio", back_populates="cliente_vizu", uselist=False, cascade="all, delete-orphan")
    fontes_de_dados = relationship("FonteDeDados", back_populates="cliente_vizu", cascade="all, delete-orphan")
    clientes_finais = relationship("ClienteFinal", back_populates="cliente_vizu", cascade="all, delete-orphan")
    credenciais = relationship("CredencialServicoExterno", back_populates="cliente_vizu", cascade="all, delete-orphan")


# Tabela 2: Contexto de Negócio do PME
class ConfiguracaoNegocio(Base):
    __tablename__ = "configuracoes_negocio"
    id = Column(Integer, primary_key=True)
    cliente_vizu_id = Column(UUID(as_uuid=True), ForeignKey("clientes_vizu.id"), nullable=False, unique=True)
    prompt_base = Column(Text, nullable=False, default="Você é um assistente virtual. Seja prestativo e educado.")
    horario_funcionamento = Column(JSON)
    ferramenta_rag_habilitada = Column(Boolean, default=True)
    ferramenta_agendamento_habilitada = Column(Boolean, default=False)
    ferramenta_consulta_db_habilitada = Column(Boolean, default=False)
    cliente_vizu = relationship("ClienteVizu", back_populates="configuracoes")


# Tabela 3: Fontes de Conhecimento para RAG
class FonteDeDados(Base):
    __tablename__ = "fontes_de_dados"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_vizu_id = Column(UUID(as_uuid=True), ForeignKey("clientes_vizu.id"), nullable=False)
    tipo_fonte = Column(String(50), nullable=False)
    uri = Column(String(1024), nullable=False)
    status_indexacao = Column(String(50), nullable=False, default="pendente")
    criado_em = Column(DateTime, default=datetime.utcnow)
    cliente_vizu = relationship("ClienteVizu", back_populates="fontes_de_dados")


# Tabela 4: Clientes dos Nossos Clientes
class ClienteFinal(Base):
    __tablename__ = "clientes_finais"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_vizu_id = Column(UUID(as_uuid=True), ForeignKey("clientes_vizu.id"), nullable=False)
    id_externo = Column(String(255), nullable=False)
    nome = Column(String(255))
    metadados = Column(JSON)
    conversas = relationship("Conversa", back_populates="cliente_final", cascade="all, delete-orphan")

    # ADICIONE ESTA LINHA QUE FALTAVA:
    cliente_vizu = relationship("ClienteVizu", back_populates="clientes_finais")
    __table_args__ = (
        UniqueConstraint("cliente_vizu_id", "id_externo", name="_cliente_vizu_id_externo_uc"),
    )


# Tabela 5: Cofre de Credenciais
class CredencialServicoExterno(Base):
    __tablename__ = "credenciais_servicos_externos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_vizu_id = Column(UUID(as_uuid=True), ForeignKey("clientes_vizu.id"), nullable=False)
    nome_servico = Column(String(100), nullable=False)
    credenciais_cifradas = Column(Text, nullable=False)
    cliente_vizu = relationship("ClienteVizu", back_populates="credenciais")
    __table_args__ = (
        UniqueConstraint("cliente_vizu_id", "nome_servico", name="_cliente_servico_uc"),
    )

# Tabela 6 e 7: Histórico de Conversas (com ajustes)
class Conversa(Base):
    __tablename__ = "conversas"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_final_id = Column(Integer, ForeignKey("clientes_finais.id"), nullable=False)
    timestamp_inicio = Column(DateTime, default=datetime.utcnow)
    cliente_final = relationship("ClienteFinal", back_populates="conversas")
    mensagens = relationship("Mensagem", back_populates="conversa", cascade="all, delete-orphan")

class Mensagem(Base):
    __tablename__ = "mensagens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversa_id = Column(UUID(as_uuid=True), ForeignKey("conversas.id"), nullable=False)
    remetente = Column(String(50), nullable=False)
    conteudo = Column(Text, nullable=False)
    metadados_ia = Column(JSON)
    timestamp_envio = Column(DateTime, default=datetime.utcnow)
    conversa = relationship("Conversa", back_populates="mensagens")