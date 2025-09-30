# O import agora aponta para o novo local do tasks.py
from vizu_infra.tasks import indexar_fonte_de_dados
import uuid

FONTE_ID_TESTE = str(uuid.uuid4())

if __name__ == "__main__":
    print(f"Disparando tarefa de indexação para a fonte: {FONTE_ID_TESTE}")
    indexar_fonte_de_dados.delay(FONTE_ID_TESTE)
    print("Tarefa enviada para o worker. Verifique o outro terminal para ver o progresso.")