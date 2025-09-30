from fastapi import FastAPI
from .schemas import HealthCheckResponse
from .routes import fontes_de_dados, clientes # Importa nossos roteadores

# Cria a instância principal da aplicação
app = FastAPI(
    title="Vizu Infra API",
    version="0.1.0",
    description="API central para gerenciamento de clientes e pipelines da plataforma Vizu."
)

# Inclui as rotas na aplicação principal, com o prefixo de versão /v1
# Todas as rotas em 'clientes.router' começarão com /v1
app.include_router(clientes.router, prefix="/v1")
# Todas as rotas em 'fontes_de_dados.router' também começarão com /v1
app.include_router(fontes_de_dados.router, prefix="/v1")


# Mantemos o health check simples na raiz da aplicação
@app.get("/health", response_model=HealthCheckResponse, tags=["Status"])
def health_check():
    """
    Endpoint de verificação de saúde. Retorna 'ok' se a API estiver no ar.
    """
    return HealthCheckResponse(status="ok")