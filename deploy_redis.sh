#!/bin/bash

# Скрипт для развертывания Redis на production сервере
# Использование: ./deploy_redis.sh

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Требуем пароль Redis из переменной окружения
if [ -z "${REDIS_PASSWORD}" ]; then
    echo -e "${RED}Ошибка: установите переменную окружения REDIS_PASSWORD перед запуском${NC}"
    exit 1
fi
REDIS_PASSWORD_ESCAPED=$(printf '%q' "${REDIS_PASSWORD}")

# SSH параметры
SSH_PASSWORD='trs5m4t1'
SSH_USER='qlknpodo'
SSH_HOST='195.191.24.169'
PROJECT_PATH='/home/qlknpodo/TWC/TwoComms_Site/twocomms'
VENV_PATH='/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate'

echo -e "${GREEN}=== Начало развертывания Redis ===${NC}"

# 1. Проверка доступности сервера
echo -e "${YELLOW}[1/7] Проверка доступности сервера...${NC}"
if ! sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "echo 'Server is reachable'"; then
    echo -e "${RED}Ошибка: Не удалось подключиться к серверу${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Сервер доступен${NC}"

# 2. Установка Docker и Docker Compose (если еще не установлены)
echo -e "${YELLOW}[2/7] Проверка и установка Docker...${NC}"

# Проверка Docker
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "command -v docker" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Установка Docker..."
    sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh && rm get-docker.sh"
else
    echo "Docker уже установлен"
fi

# Проверка Docker Compose
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "command -v docker-compose" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Установка Docker Compose..."
    sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "sudo curl -L 'https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64' -o /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose"
else
    echo "Docker Compose уже установлен"
fi
echo -e "${GREEN}✓ Docker установлен${NC}"

# 3. Обновление кода из git
echo -e "${YELLOW}[3/7] Обновление кода из git...${NC}"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "cd ${PROJECT_PATH} && git pull origin main"
echo -e "${GREEN}✓ Код обновлен${NC}"

# 4. Копирование docker-compose.yml и redis.conf на сервер
echo -e "${YELLOW}[4/7] Копирование docker-compose.yml и redis.conf...${NC}"
sshpass -p "${SSH_PASSWORD}" scp -o StrictHostKeyChecking=no docker-compose.yml ${SSH_USER}@${SSH_HOST}:${PROJECT_PATH}/
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "mkdir -p ${PROJECT_PATH}/infra/redis"
sshpass -p "${SSH_PASSWORD}" scp -o StrictHostKeyChecking=no infra/redis/redis.conf ${SSH_USER}@${SSH_HOST}:${PROJECT_PATH}/infra/redis/redis.conf
echo -e "${GREEN}✓ Конфигурация Redis обновлена${NC}"

# 5. Обновление зависимостей Python
echo -e "${YELLOW}[5/7] Обновление зависимостей Python...${NC}"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "source ${VENV_PATH} && cd ${PROJECT_PATH} && pip install --upgrade pip"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "source ${VENV_PATH} && cd ${PROJECT_PATH} && pip install -r requirements.txt"
echo -e "${GREEN}✓ Зависимости обновлены${NC}"

# 6. Запуск Redis в Docker
echo -e "${YELLOW}[6/7] Запуск Redis контейнера...${NC}"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "cd ${PROJECT_PATH} && export REDIS_PASSWORD=${REDIS_PASSWORD_ESCAPED} && docker-compose down" || true
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "cd ${PROJECT_PATH} && export REDIS_PASSWORD=${REDIS_PASSWORD_ESCAPED} && docker-compose up -d"
echo -e "${GREEN}✓ Redis запущен${NC}"

# 7. Перезапуск Django приложения
echo -e "${YELLOW}[7/7] Перезапуск Django приложения...${NC}"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "source ${VENV_PATH} && cd ${PROJECT_PATH} && python manage.py migrate"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "source ${VENV_PATH} && cd ${PROJECT_PATH} && python manage.py collectstatic --noinput"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "touch ${PROJECT_PATH}/passenger_wsgi.py"
echo -e "${GREEN}✓ Django приложение перезапущено${NC}"

# 8. Проверка статуса
echo -e "${YELLOW}Проверка статуса Redis...${NC}"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "cd ${PROJECT_PATH} && docker-compose ps"
sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "cd ${PROJECT_PATH} && export REDIS_PASSWORD=${REDIS_PASSWORD_ESCAPED} && docker-compose exec -T redis redis-cli -a ${REDIS_PASSWORD_ESCAPED} ping"

echo -e "${GREEN}=== Развертывание завершено успешно! ===${NC}"
echo -e "${GREEN}Redis доступен на localhost:6379 (подключение требует пароль)${NC}"
echo -e "${YELLOW}Для проверки работы выполните:${NC}"
echo -e "  docker-compose logs -f redis"
