import uuid
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

# Carrega as variáveis de ambiente do arquivo .env no início
load_dotenv()

class VetorDBService:
    def __init__(self):
        """
        Inicializa o serviço de banco de dados vetorial usando o modo REST,
        lendo a URL completa e a chave de API do ambiente.
        """
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not qdrant_url or not qdrant_api_key:
            raise ValueError("As variáveis QDRANT_URL e QDRANT_API_KEY precisam estar definidas no .env")

        # Inicializa o cliente usando os parâmetros que o 'curl' provou que funcionam
        self.client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )
        print(f"Conexão REST com o Qdrant Cloud estabelecida com sucesso em: {qdrant_url}")

    def criar_colecao_para_cliente(self, cliente_vizu_id: uuid.UUID, tamanho_vetor: int):
        """
        Cria uma nova coleção com um TAMANHO DE VETOR específico.
        """
        nome_colecao = str(cliente_vizu_id)
        try:
            self.client.recreate_collection(
                collection_name=nome_colecao,
                vectors_config=models.VectorParams(
                    size=tamanho_vetor,
                    distance=models.Distance.COSINE
                )
            )
            print(f"Coleção '{nome_colecao}' criada com sucesso (tamanho do vetor: {tamanho_vetor}).")
            return True
        except Exception as e:
            print(f"Erro ao criar coleção '{nome_colecao}': {e}")
            raise # Relança o erro para o pipeline principal

    def indexar_documento(self, cliente_vizu_id: uuid.UUID, fonte_dados_id: uuid.UUID, chunks: list[dict]):
        """
        Indexa os chunks de um documento na coleção do cliente.
        """
        nome_colecao = str(cliente_vizu_id)
        pontos = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=chunk['vetor'],
                payload={
                    "fonte_dados_id": str(fonte_dados_id),
                    "texto_original": chunk['texto'],
                }
            ) for chunk in chunks
        ]

        if not pontos:
            print("Nenhum chunk para indexar.")
            return

        try:
            self.client.upsert(
                collection_name=nome_colecao,
                points=pontos,
                wait=True
            )
            print(f"{len(pontos)} chunks indexados para o cliente {cliente_vizu_id}.")
        except Exception as e:
            print(f"Erro ao indexar documentos para o cliente {cliente_vizu_id}: {e}")
            raise # Relança o erro

    def buscar_chunks_relevantes(self, cliente_vizu_id: uuid.UUID, vetor_query: list[float], top_k: int = 5) -> list[dict]:
        """
        Busca os chunks mais relevantes para uma pergunta.
        """
        nome_colecao = str(cliente_vizu_id)
        try:
            resultados = self.client.search(
                collection_name=nome_colecao,
                query_vector=vetor_query,
                limit=top_k
            )
            return [hit.payload for hit in resultados]
        except Exception as e:
            print(f"Erro ao buscar na coleção {nome_colecao}: {e}")
            return []