import uuid
from datetime import datetime

from sqlalchemy import (
    create_engine,
    Column,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    BigInteger
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class ClienteVizu(Base):
    __tablename__ = 'clientes_vizu'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_empresa = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False, unique=True)
    tier = Column(String(50), nullable=False, default='sme') # 'sme' ou 'enterprise'
    criado_em = Column(DateTime, default=datetime.utcnow)
    tipo_cliente = Column(String(50), nullable=False, default='externo') # 'externo' ou 'interno'


    # Relacionamentos
    fontes_de_dados = relationship("FonteDeDados", back_populates="cliente_vizu")
    conversas = relationship("Conversa", back_populates="cliente_vizu")
    clientes_finais = relationship("ClienteFinalMetadados", back_populates="cliente_vizu")

class FonteDeDados(Base):
    __tablename__ = 'fontes_de_dados'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_vizu_id = Column(UUID(as_uuid=True), ForeignKey('clientes_vizu.id'), nullable=False)
    tipo_fonte = Column(String(50), nullable=False) # Ex: 'pdf_cardapio', 'url_faq'
    uri = Column(String(1024), nullable=False) # Ex: s3://bucket-vizu/cliente_id/cardapio.pdf
    status_indexacao = Column(String(50), nullable=False, default='pendente')
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Relacionamento
    cliente_vizu = relationship("ClienteVizu", back_populates="fontes_de_dados")


class Conversa(Base):
    __tablename__ = 'conversas'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_vizu_id = Column(UUID(as_uuid=True), ForeignKey('clientes_vizu.id'), nullable=False)
    id_usuario_final = Column(String(255), nullable=False)
    timestamp_inicio = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    cliente_vizu = relationship("ClienteVizu", back_populates="conversas")
    mensagens = relationship("Mensagem", back_populates="conversa", cascade="all, delete-orphan")

class Mensagem(Base):
    __tablename__ = 'mensagens'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversa_id = Column(UUID(as_uuid=True), ForeignKey('conversas.id'), nullable=False)
    remetente = Column(String(50), nullable=False) # 'user' ou 'ai'
    conteudo = Column(Text, nullable=False)
    timestamp_envio = Column(DateTime, default=datetime.utcnow)
    metadados_ia = Column(JSON)

    # Relacionamento
    conversa = relationship("Conversa", back_populates="mensagens")

class ClienteFinalMetadados(Base):
    __tablename__ = 'clientes_finais_metadados'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cliente_vizu_id = Column(UUID(as_uuid=True), ForeignKey('clientes_vizu.id'), nullable=False)
    id_externo_cliente_final = Column(String(255), nullable=False)
    dados_customizados = Column(JSON)

    # Relacionamento
    cliente_vizu = relationship("ClienteVizu", back_populates="clientes_finais")