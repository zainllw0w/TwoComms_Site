#!/bin/bash

# Скрипт для развертывания Redis на production сервере
# Использование: ./deploy_redis.sh

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# SSH параметры
SSH_PASSWORD='trs5m4t1'
SSH_USER='qlknpodo'
SSH_HOST='195.191.24.169'
PROJECT_PATH='/home/qlknpodo/TWC/TwoComms_Site/twocomms'
VENV_PATH='/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate'

echo -e "${GREEN}=== Начало развертывания Redis ===${NC}"

# Функция для выполнения команд на сервере
run_ssh_cmd() {
    sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} "bash -lc '$1'"
}

# 1. Проверка доступности сервера
echo -e "${YELLOW}[1/7] Проверка доступности сервера...${NC}"
if ! run_ssh_cmd "echo 'Server is reachable'"; then
    echo -e "${RED}Ошибка: Не удалось подключиться к серверу${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Сервер доступен${NC}"

# 2. Установка Docker и Docker Compose (если еще не установлены)
echo -e "${YELLOW}[2/7] Проверка и установка Docker...${NC}"
run_ssh_cmd "if ! command -v docker &> /dev/null; then echo 'Установка Docker...'; curl -fsSL https://get.docker.com -o get-docker.sh; sh get-docker.sh; sudo usermod -aG docker ${SSH_USER}; rm get-docker.sh; else echo 'Docker уже установлен'; fi"

run_ssh_cmd "if ! command -v docker-compose &> /dev/null; then echo 'Установка Docker Compose...'; sudo curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)' -o /usr/local/bin/docker-compose; sudo chmod +x /usr/local/bin/docker-compose; else echo 'Docker Compose уже установлен'; fi"
echo -e "${GREEN}✓ Docker установлен${NC}"

# 3. Обновление кода из git
echo -e "${YELLOW}[3/7] Обновление кода из git...${NC}"
run_ssh_cmd "source ${VENV_PATH} && cd ${PROJECT_PATH} && git pull origin main"
echo -e "${GREEN}✓ Код обновлен${NC}"

# 4. Копирование docker-compose.yml на сервер
echo -e "${YELLOW}[4/7] Копирование docker-compose.yml...${NC}"
sshpass -p "${SSH_PASSWORD}" scp -o StrictHostKeyChecking=no docker-compose.yml ${SSH_USER}@${SSH_HOST}:${PROJECT_PATH}/
echo -e "${GREEN}✓ docker-compose.yml скопирован${NC}"

# 5. Обновление зависимостей Python
echo -e "${YELLOW}[5/7] Обновление зависимостей Python...${NC}"
run_ssh_cmd "source ${VENV_PATH} && cd ${PROJECT_PATH} && pip install --upgrade pip && pip install -r requirements.txt"
echo -e "${GREEN}✓ Зависимости обновлены${NC}"

# 6. Запуск Redis в Docker
echo -e "${YELLOW}[6/7] Запуск Redis контейнера...${NC}"
run_ssh_cmd "cd ${PROJECT_PATH} && docker-compose down || true && docker-compose up -d"
echo -e "${GREEN}✓ Redis запущен${NC}"

# 7. Перезапуск Django приложения
echo -e "${YELLOW}[7/7] Перезапуск Django приложения...${NC}"
run_ssh_cmd "source ${VENV_PATH} && cd ${PROJECT_PATH} && python manage.py migrate && python manage.py collectstatic --noinput && touch ${PROJECT_PATH}/passenger_wsgi.py"
echo -e "${GREEN}✓ Django приложение перезапущено${NC}"

# 8. Проверка статуса
echo -e "${YELLOW}Проверка статуса Redis...${NC}"
run_ssh_cmd "cd ${PROJECT_PATH} && docker-compose ps"

echo -e "${GREEN}=== Развертывание завершено успешно! ===${NC}"
echo -e "${GREEN}Redis доступен на localhost:6379${NC}"
echo -e "${YELLOW}Для проверки работы выполните:${NC}"
echo -e "  docker-compose logs -f redis"

