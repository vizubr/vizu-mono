import os
from dotenv import load_dotenv
from vizu_infra.celery_app import app
import time
import uuid
from pathlib import Path
from vizu_infra.services.file_parser import extrair_texto_de_pdf
from vizu_infra.services.text_splitter import dividir_texto_em_chunks
from vizu_infra.services.embedding_service import EmbeddingService
from vizu_infra.vector_db.qdrant import VetorDBService

project_root = Path(__file__).resolve().parent.parent.parent
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path=dotenv_path)

class MockFonte:
    def __init__(self, id, uri, cliente_vizu_id):
        self.id = id
        self.uri = uri
        self.cliente_vizu_id = cliente_vizu_id

def get_fonte_por_id(id):
    print(f"BUSCANDO FONTE {id} NO BANCO DE DADOS...")
    return MockFonte(
        id=id,
        uri="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        cliente_vizu_id=uuid.UUID("a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d")
    )

def atualizar_status(id, status):
    print(f"ATUALIZANDO STATUS DA FONTE {id} PARA '{status}' NO BANCO DE DADOS.")
# --- FIM DA SIMULAÇÃO ---

@app.task
def indexar_fonte_de_dados(fonte_dados_id: str):
    """
    Worker Celery que executa o pipeline de indexação completo.
    """
    print(f"--- INICIANDO PIPELINE PARA FONTE DE DADOS: {fonte_dados_id} ---")

    # Lê o nome do modelo do ambiente. Se não encontrar, usa um padrão seguro.
    model_name = os.getenv("EMBEDDING_MODEL_NAME")
    if not model_name:
        raise ValueError("A variável de ambiente EMBEDDING_MODEL_NAME não foi definida.")

    # Instancia os serviços AQUI DENTRO, usando a configuração carregada
    embedding_service = EmbeddingService(model_name=model_name)
    vector_db_service = VetorDBService()

    try:
        fonte = get_fonte_por_id(fonte_dados_id)
        atualizar_status(fonte_dados_id, "processando")

        texto_bruto = extrair_texto_de_pdf(fonte.uri)
        chunks_texto = dividir_texto_em_chunks(texto_bruto)

        if not chunks_texto:
            print("Nenhum texto extraído ou chunks gerados. Finalizando com sucesso.")
            atualizar_status(fonte_dados_id, "concluido_sem_texto")
            return

        vetores = embedding_service.gerar_vetores(chunks_texto)

        documentos = [{"texto": t, "vetor": v} for t, v in zip(chunks_texto, vetores)]

        vector_db_service.indexar_documento(
            cliente_vizu_id=fonte.cliente_vizu_id,
            fonte_dados_id=fonte.id,
            chunks=documentos
        )

        atualizar_status(fonte_dados_id, "concluido")
        print(f"--- PIPELINE FINALIZADO COM SUCESSO PARA: {fonte_dados_id} ---")

    except Exception as e:
        atualizar_status(fonte_dados_id, "falhou")
        print(f"--- ERRO NO PIPELINE PARA {fonte_dados_id}: {e} ---")
        raise