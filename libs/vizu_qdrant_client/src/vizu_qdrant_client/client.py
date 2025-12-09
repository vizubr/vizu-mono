import os
import logging
from typing import List, Optional
from qdrant_client import QdrantClient, models
from langchain_qdrant import QdrantVectorStore
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever

logger = logging.getLogger(__name__)

# ============================================================================
# SINGLETON CLIENT
# ============================================================================

_qdrant_client_instance: Optional["VizuQdrantClient"] = None


def get_qdrant_client() -> "VizuQdrantClient":
    """
    Retorna uma instância singleton do VizuQdrantClient.
    Evita criar múltiplas conexões com o Qdrant.
    """
    global _qdrant_client_instance

    if _qdrant_client_instance is None:
        _qdrant_client_instance = VizuQdrantClient()
        logger.info("VizuQdrantClient singleton criado.")

    return _qdrant_client_instance


class VizuQdrantClient:
    """
    Cliente agnóstico para interagir com o Qdrant.
    Configurado via variáveis de ambiente.

    Uso recomendado: usar get_qdrant_client() para obter instância singleton.
    """
    def __init__(self):
        qdrant_url = os.getenv("QDRANT_URL_PROD", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        self.client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=30,  # Timeout para operações
        )
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key

        logger.info(f"QdrantClient conectado em: {qdrant_url}")

    def create_collection_if_not_exists(self, collection_name: str, vector_size: int):
        try:
            self.client.get_collection(collection_name=collection_name)
            logger.info(f"Coleção '{collection_name}' já existe.")
        except Exception:
            logger.info(f"Coleção '{collection_name}' não encontrada. Criando...")
            self.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )
            logger.info(f"Coleção '{collection_name}' criada com sucesso.")

    def upsert_vectors(self, collection_name: str, points: List[models.PointStruct]):
        self.client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True
        )

    def search(self, collection_name: str, query_vector: List[float], limit: int = 5) -> List[models.ScoredPoint]:
        """
        Realiza uma busca por similaridade em uma coleção.
        """
        hits = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
        return hits

    def get_langchain_retriever(
        self,
        collection_name: str,
        embeddings: Embeddings,
        search_k: int = 4,
        search_type: str = "similarity"
    ) -> VectorStoreRetriever:
        """
        Cria um retriever LangChain para uma coleção específica.

        O isolamento é garantido pela collection_name - cada cliente
        tem sua própria coleção no Qdrant.

        Args:
            collection_name: Nome da coleção do cliente (ex: "studio_j_conhecimento")
            embeddings: Modelo de embeddings a usar
            search_k: Número de documentos a retornar
            search_type: Tipo de busca ("similarity", "mmr", etc.)

        Returns:
            VectorStoreRetriever configurado para a coleção
        """
        logger.debug(f"Criando retriever para coleção: {collection_name}")

        # Cria o VectorStore do LangChain usando o cliente existente
        # content_payload_key mapeia nosso campo 'content' para o 'page_content' esperado pelo LangChain
        # metadata_payload_key mapeia campos adicionais (title, doc_id, etc) para metadata
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embedding=embeddings,
            content_payload_key="content",  # Nosso campo é 'content', não 'page_content'
            metadata_payload_key="metadata",  # Campo para metadados extras
        )

        # Retorna como retriever
        retriever = vector_store.as_retriever(
            search_type=search_type,
            search_kwargs={"k": search_k}
        )

        logger.info(f"Retriever criado para coleção '{collection_name}' (k={search_k})")
        return retriever

    def collection_exists(self, collection_name: str) -> bool:
        """Verifica se uma coleção existe."""
        try:
            self.client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

    def get_collection_info(self, collection_name: str) -> Optional[dict]:
        """Retorna informações sobre uma coleção."""
        try:
            info = self.client.get_collection(collection_name=collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
        except Exception as e:
            logger.warning(f"Erro ao obter info da coleção {collection_name}: {e}")
            return None