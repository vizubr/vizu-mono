import uuid
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from ..database.models import ClienteVizu
from ..database.repository import get_db_session, get_cliente_por_api_key

def get_cliente_autenticado(
    cliente_id: uuid.UUID,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db_session)
) -> ClienteVizu:
    """
    Dependência reutilizável que valida a API Key e autoriza o acesso ao recurso.
    Garante que a API Key pertence ao cliente_id sendo acessado.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autorização 'Bearer' ausente ou mal formatado")

    api_key = authorization.split(" ")[1]

    cliente = get_cliente_por_api_key(db, api_key=api_key)
    if not cliente:
        raise HTTPException(status_code=401, detail="API Key inválida")

    if cliente.id != cliente_id:
        raise HTTPException(status_code=403, detail="Acesso negado: você não tem permissão para acessar este recurso.")

    return cliente