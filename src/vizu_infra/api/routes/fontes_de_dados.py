import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# Importando de nossos novos módulos organizados
from ..schemas import FonteDeDadosInput, FonteDeDadosResponse
from ..security import get_cliente_autenticado
from ...database.models import ClienteVizu
from ...database.repository import get_db_session, criar_fonte_de_dados
from ...tasks import indexar_fonte_de_dados

# Criamos um "roteador". Pense nele como uma mini-aplicação FastAPI.
router = APIRouter(
    prefix="/v1/clientes/{cliente_id}/fontes-de-dados", # Prefixo de URL para todas as rotas neste arquivo
    tags=["Fontes de Dados"] # Agrupa na documentação do Swagger
)

@router.post("", status_code=202, response_model=FonteDeDadosResponse)
def submeter_fonte_de_dados(
    cliente_id: uuid.UUID,
    fonte_input: FonteDeDadosInput,
    cliente: ClienteVizu = Depends(get_cliente_autenticado),
    db: Session = Depends(get_db_session)
):
    """
    Submete uma nova fonte de dados (ex: PDF, URL) para um cliente específico.
    O pipeline de indexação será iniciado em segundo plano.
    """
    print(f"Cliente '{cliente.nome_empresa}' autenticado. Submetendo nova fonte de dados.")

    nova_fonte = criar_fonte_de_dados(
        db_session=db,
        cliente_id=cliente.id,
        tipo=fonte_input.tipo_fonte,
        uri=fonte_input.uri
    )

    indexar_fonte_de_dados.delay(str(nova_fonte.id))

    return FonteDeDadosResponse(
        id=nova_fonte.id,
        status="pendente",
        mensagem="Fonte de dados recebida e enfileirada para processamento."
    )