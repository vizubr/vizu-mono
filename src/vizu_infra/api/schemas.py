import uuid
from pydantic import BaseModel

# Schema para o endpoint de Health Check
class HealthCheckResponse(BaseModel):
    status: str

# Schemas para o recurso de Fontes de Dados
class FonteDeDadosInput(BaseModel):
    tipo_fonte: str
    uri: str

class FonteDeDadosResponse(BaseModel):
    id: uuid.UUID
    status: str
    mensagem: str

class ClienteInput(BaseModel):
    nome_empresa: str
    tier: str = "sme"
    tipo_cliente: str = "externo"

class ClienteResponse(BaseModel):
    id: uuid.UUID
    nome_empresa: str
    api_key: str
    mensagem: str

# Adicionaremos mais schemas aqui conforme a API crescer