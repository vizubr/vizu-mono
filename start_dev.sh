#!/bin/bash

# Define cores para os logs, para ficar mais fácil de ler
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}---> PASSO 1: Iniciando serviços de infraestrutura (Postgres & Redis)...${NC}"
docker-compose up -d
echo "Serviços Docker iniciados."
echo ""
sleep 10 # Aguarda 10 segundos para garantir que os serviços estejam prontos
# Garante que o ambiente virtual está ativo para os próximos comandos
source .venv/bin/activate
alembic upgrade head


echo -e "${GREEN}---> PASSO 2: Iniciando o servidor da API FastAPI/Uvicorn...${NC}"
# Inicia o Uvicorn em segundo plano (&) e redireciona sua saída para um arquivo de log
uvicorn vizu_infra.api.main:app --reload --app-dir src > api.log 2>&1 &
UVICORN_PID=$! # Salva o ID do processo do Uvicorn
echo "Servidor da API iniciado em segundo plano. Logs em: api.log (PID: $UVICORN_PID)"
echo ""

echo -e "${GREEN}---> PASSO 3: Iniciando o worker do Celery...${NC}"
# Inicia o Celery em segundo plano (&) e redireciona sua saída para um arquivo de log
celery -A vizu_infra.celery_app worker --loglevel=INFO > worker.log 2>&1 &
CELERY_PID=$! # Salva o ID do processo do Celery
echo "Worker do Celery iniciado em segundo plano. Logs em: worker.log (PID: $CELERY_PID)"
echo ""

echo -e "${GREEN}---> AMBIENTE DE DESENVOLVIMENTO PRONTO! <---${NC}"
echo "Para ver os logs em tempo real, use o comando:"
echo "tail -f api.log worker.log"
echo ""
echo "Para parar todos os serviços, execute: ./stop_dev.sh"