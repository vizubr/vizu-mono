import uuid
import os
from dotenv import load_dotenv # <-- 1. IMPORTAR A FUNÇÃO
from pathlib import Path # <-- 1. Importe a biblioteca Path

from src.vizu_infra.vector_db.qdrant import VetorDBService
from src.vizu_infra.services.embedding_service import EmbeddingService

project_root = Path(__file__).resolve().parent
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path=dotenv_path)

# ID do nosso cliente de teste (o mesmo que está no mock do tasks.py)
CLIENTE_ID_TESTE = uuid.UUID("a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d")

MODELO_ATUAL = os.getenv("EMBEDDING_MODEL_NAME")
embedding_service = EmbeddingService(MODELO_ATUAL)
TAMANHO_VETOR_ATUAL = embedding_service.dimensao

if __name__ == "__main__":
    # Adicionamos uma verificação para te dar uma mensagem de erro clara
    if not MODELO_ATUAL:
        print("--- ERRO! ---")
        print("A variável EMBEDDING_MODEL_NAME não foi encontrada.")
        print("Verifique se o seu arquivo .env existe na raiz do projeto e contém a linha:")
        print('EMBEDDING_MODEL_NAME="neuralmind/bert-base-portuguese-cased"')
    else:
        print("Configurando ambiente de teste...")
        print(f"Usando o modelo: {MODELO_ATUAL}")

        embedding_service = EmbeddingService(MODELO_ATUAL)
        tamanho_vetor_atual = embedding_service.dimensao

        qdrant_service = VetorDBService()
        qdrant_service.criar_colecao_para_cliente(
            CLIENTE_ID_TESTE,
            tamanho_vetor=tamanho_vetor_atual
        )
        print("Ambiente pronto.")



