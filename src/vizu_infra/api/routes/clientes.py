import uuid
import os
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# Importando de nossos módulos organizados
from ..schemas import ClienteInput, ClienteResponse
from ...database.repository import get_db_session, criar_cliente_completo
from ...vector_db.qdrant import VetorDBService
from ...services.embedding_service import EmbeddingService

# Criamos um roteador específico para o recurso "Clientes"
router = APIRouter(
    prefix="/clientes",       # O prefixo /v1 será adicionado no main.py
    tags=["Clientes"]         # Agrupa na documentação do Swagger
)


@router.post("", status_code=201, response_model=ClienteResponse)
def criar_novo_cliente(
    cliente_input: ClienteInput,
    db: Session = Depends(get_db_session)
):
    """
    Realiza o onboarding de um novo cliente na plataforma Vizu.
    """
    print(f"Recebida requisição para criar novo cliente: {cliente_input.nome_empresa}")

    # 1. Gerar API Key segura
    nova_api_key = secrets.token_hex(32)

    # 2. Salvar no banco SQL usando o repositório
    novo_cliente = criar_cliente_completo(
        db_session=db,
        nome=cliente_input.nome_empresa,
        api_key=nova_api_key,
        tier=cliente_input.tier,
        tipo=cliente_input.tipo_cliente
    )
    print(f"Cliente '{novo_cliente.nome_empresa}' criado no SQL com ID: {novo_cliente.id}")


    # 3. Criar a coleção no Qdrant
    try:
        # --- SEÇÃO MODIFICADA ---
        model_name = os.getenv("EMBEDDING_MODEL_NAME")
        if not model_name:
            # Falha rápida se a configuração estiver faltando
            raise RuntimeError("A variável de ambiente EMBEDDING_MODEL_NAME não foi definida.")

        vetor_db_service = VetorDBService()
        embedding_service = EmbeddingService(model_name=model_name) # <-- CORREÇÃO AQUI

        vetor_db_service.criar_colecao_para_cliente(
            cliente_vizu_id=novo_cliente.id,
            tamanho_vetor=embedding_service.dimensao
        )
        # --- FIM DA SEÇÃO MODIFICADA ---
        print(f"Coleção criada no Qdrant para o cliente: {novo_cliente.id}")
    except Exception as e:
        # Em um cenário real, teríamos uma lógica para reverter a criação do cliente no SQL (rollback)
        print(f"ERRO CRÍTICO: Cliente criado no SQL, mas falhou ao criar coleção no Qdrant: {e}")
        raise HTTPException(status_code=500, detail="Erro ao provisionar recursos no banco vetorial.")

    # 4. Retornar a resposta para o usuário
    return ClienteResponse(
        id=novo_cliente.id,
        nome_empresa=cliente_input.nome_empresa,
        api_key=nova_api_key,
        mensagem="Cliente criado com sucesso. Guarde esta API Key em um local seguro."
    )