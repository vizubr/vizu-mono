from sentence_transformers import SentenceTransformer
from typing import Dict, Any

class EmbeddingService:
    # Usamos um cache simples para não recarregar o mesmo modelo várias vezes
    _model_cache: Dict[str, SentenceTransformer] = {}

    def __init__(self, model_name: str):
        """
        Inicializa o serviço de embedding com um NOME DE MODELO específico.
        """
        self.model_name = model_name
        print(f"Carregando o modelo de embedding local: {self.model_name} na CPU...")

        # O modelo será baixado e salvo em cache na primeira execução
        # Adicionamos device='cpu' para garantir estabilidade no macOS com Celery
        self.model = self._get_model(model_name)

        self.dimensao = self.model.get_sentence_embedding_dimension()
        print(f"Serviço de Embedding pronto com o modelo '{self.model_name}' (Dimensão: {self.dimensao}).")

    @classmethod
    def _get_model(cls, model_name: str) -> SentenceTransformer:
        if model_name not in cls._model_cache:
            print(f"Modelo '{model_name}' não está em cache. Carregando na CPU...")
            cls._model_cache[model_name] = SentenceTransformer(model_name, device='cpu')
        return cls._model_cache[model_name]


    def gerar_vetores(self, chunks_texto: list[str]) -> list[list[float]]:
        # ... (o resto do método continua igual) ...
        try:
            vetores = self.model.encode(chunks_texto, show_progress_bar=False)
            return [vetor.tolist() for vetor in vetores]
        except Exception as e:
            print(f"Erro ao gerar embeddings com o modelo {self.model_name}: {e}")
            raise