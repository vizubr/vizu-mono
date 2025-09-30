#!/bin/bash

# Define cores
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${RED}---> PARANDO O SERVIDOR DA API (UVICORN)...${NC}"
# Encontra e mata o processo do Uvicorn pela string do comando
pkill -f "uvicorn vizu_infra.api.main:app"
echo "Servidor da API finalizado."
echo ""

echo -e "${RED}---> PARANDO O WORKER DO CELERY...${NC}"
# Encontra e mata o processo principal do Celery pela string do comando
pkill -f "celery -A vizu_infra.celery_app worker"
echo "Worker do Celery finalizado."
echo ""

echo -e "${RED}---> PARANDO OS SERVIÇOS DOCKER (POSTGRES & REDIS)...${NC}"
docker-compose down
echo "Serviços Docker finalizados."
echo ""

echo -e "${RED}---> AMBIENTE DESLIGADO. <---${NC}"