import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# --- NOVO BLOCO DE VERIFICAÇÃO ---
print("--- Verificando variáveis carregadas ---")
print(f"Host lido do .env: {QDRANT_HOST}")
if QDRANT_API_KEY:
    # Imprime apenas o início e o fim da chave para segurança
    print(f"API Key lida do .env: {QDRANT_API_KEY[:4]}...{QDRANT_API_KEY[-4:]}")
else:
    print("API Key lida do .env: Nenhuma chave encontrada!")
print("-------------------------------------\n")
# --- FIM DO BLOCO DE VERIFICAÇÃO ---
if not QDRANT_HOST or not QDRANT_API_KEY:
    print("--- ERRO ---")
    print("As variáveis QDRANT_HOST e QDRANT_API_KEY precisam estar definidas no seu arquivo .env")
else:
    print(f"Tentando conectar ao host: {QDRANT_HOST}\n")

    # --- TENTATIVA 1: MODO gRPC (Recomendado para Cloud) ---
    print("--- Testando Conexão via gRPC (Porta 6333) ---")
    try:
        client_grpc = QdrantClient(
            host=QDRANT_HOST,
            port=6333,
            api_key=QDRANT_API_KEY,
            https=True, # Força o uso de TLS (conexão segura)
        )
        # A operação mais simples: pedir a lista de coleções
        collections_grpc = client_grpc.get_collections()
        print("✅ SUCESSO! Conexão gRPC estabelecida.")
        print(f"Coleções encontradas: {collections_grpc}\n")
    except Exception as e:
        print(f"❌ FALHA na conexão gRPC: {e}\n")


    # --- TENTATIVA 2: MODO REST (Com URL completa) ---
    print("--- Testando Conexão via REST (sem porta explícita) ---")
    try:
        # Monta a URL completa para o modo REST
        rest_url = f"https://{QDRANT_HOST}"
        client_rest = QdrantClient(
            url=rest_url,
            api_key=QDRANT_API_KEY,
        )
        collections_rest = client_rest.get_collections()
        print("✅ SUCESSO! Conexão REST estabelecida.")
        print(f"Coleções encontradas: {collections_rest}\n")
    except Exception as e:
        print(f"❌ FALHA na conexão REST: {e}\n")