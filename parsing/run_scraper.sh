#!/bin/bash

set -e  # Остановить выполнение при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    PropertyFinder Scraper Automation  ${NC}"
echo -e "${BLUE}========================================${NC}"

# Определяем переменные
VENV_DIR="venv"
SCRAPED_DATA_DIR="scraped_data"
REQUIREMENTS_FILE="requirements.txt"

# Функция для логирования
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    log_error "Python3 не найден. Установите Python3 для продолжения."
    exit 1
fi

# 1. Создаем виртуальное окружение, если его нет
if [ ! -d "$VENV_DIR" ]; then
    log "Создаем виртуальное окружение..."
    python3 -m venv "$VENV_DIR"
    log "Виртуальное окружение создано: $VENV_DIR"
else
    log "Виртуальное окружение уже существует: $VENV_DIR"
fi

# Активируем виртуальное окружение
log "Активируем виртуальное окружение..."
source "$VENV_DIR/bin/activate"

# 2. Устанавливаем зависимости
if [ -f "$REQUIREMENTS_FILE" ]; then
    log "Устанавливаем зависимости из $REQUIREMENTS_FILE..."
    pip install --upgrade pip
    pip install -r "$REQUIREMENTS_FILE"
    log "Зависимости установлены успешно"
else
    log_warning "Файл $REQUIREMENTS_FILE не найден. Устанавливаем базовые зависимости..."
    pip install --upgrade pip
    pip install requests beautifulsoup4 lxml
fi

# Создаем директорию для результатов, если её нет
mkdir -p "$SCRAPED_DATA_DIR"

# Запоминаем текущие папки в scraped_data
EXISTING_DIRS=$(find "$SCRAPED_DATA_DIR" -maxdepth 1 -type d -name "scrape_*" 2>/dev/null || echo "")

# 3. Запускаем a_buy.py
log "Запускаем скрипт a_buy.py..."
if [ -f "a_buy.py" ]; then
    python a_buy.py
    log "Скрипт a_buy.py выполнен успешно"
else
    log_error "Файл a_buy.py не найден!"
    exit 1
fi

# 4. Запускаем a.py
log "Запускаем скрипт a.py..."
if [ -f "a.py" ]; then
    python a.py
    log "Скрипт a.py выполнен успешно"
else
    log_error "Файл a.py не найден!"
    exit 1
fi

# 5. Находим новые папки, созданные скриптами
log "Ищем новые папки, созданные скриптами..."
NEW_DIRS=$(find "$SCRAPED_DATA_DIR" -maxdepth 1 -type d -name "scrape_*" 2>/dev/null || echo "")

# Определяем папки, которые были созданы этим запуском
CREATED_DIRS=""
for dir in $NEW_DIRS; do
    # Проверяем, была ли эта папка в списке существующих
    if ! echo "$EXISTING_DIRS" | grep -q "$dir"; then
        CREATED_DIRS="$CREATED_DIRS $dir"
    fi
done

if [ -z "$CREATED_DIRS" ]; then
    log_warning "Новые папки не найдены. Обрабатываем все папки scrape_*"
    CREATED_DIRS="$NEW_DIRS"
fi

# 6. Для каждой созданной папки запускаем take_all.py
for dir in $CREATED_DIRS; do
    if [ -d "$dir" ]; then
        log "Обрабатываем папку: $dir"
        
        # Запускаем take_all.py для этой папки
        if [ -f "take_all.py" ]; then
            # Определяем имя выходного файла
            dir_name=$(basename "$dir")
            output_file="${dir}/processed_${dir_name}.json"
            
            log "Запускаем take_all.py для $dir..."
            python take_all.py "$dir" "$output_file"
            
            if [ $? -eq 0 ]; then
                log "take_all.py выполнен успешно для $dir"
                
                # 7. Удаляем все файлы кроме созданных take_all.py
                log "Очищаем папку $dir от временных файлов..."
                
                # Сохраняем файлы, созданные take_all.py (JSON файлы с processed_ в имени)
                # Удаляем json_data директорию и её содержимое
                if [ -d "$dir/json_data" ]; then
                    rm -rf "$dir/json_data"
                    log "Удалена директория json_data из $dir"
                fi
                
                # Удаляем другие временные файлы, но сохраняем важные результаты
                find "$dir" -name "*.json" ! -name "processed_*" ! -name "properties.json" -delete 2>/dev/null || true
                
                log "Очистка папки $dir завершена"
            else
                log_error "Ошибка при выполнении take_all.py для $dir"
            fi
        else
            log_error "Файл take_all.py не найден!"
        fi
    fi
done

# 8. Импорт в Django (если есть property_analyzer)
if [ -d "property_analyzer" ]; then
    log "Запускаем импорт данных в Django приложение..."
    
    cd property_analyzer
    
    # Проверяем базу данных
    if [ ! -f "db.sqlite3" ]; then
        log "Инициализируем базу данных Django..."
        python manage.py makemigrations
        python manage.py migrate
    fi
    
    # Импортируем данные
    for dir in $CREATED_DIRS; do
        if [ -d "../$dir" ]; then
            log "Импортируем данные из $dir в Django..."
            python manage.py import_properties "../$dir" --update
        fi
    done
    
    cd ..
    
    log "Django импорт завершен. Для просмотра данных запустите:"
    echo -e "  ${YELLOW}cd property_analyzer && python manage.py runserver${NC}"
    echo -e "  ${YELLOW}Затем откройте: http://127.0.0.1:8000/${NC}"
fi

# Деактивируем виртуальное окружение
deactivate

log "Все операции завершены успешно!"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}         Обработка завершена!           ${NC}"
echo -e "${BLUE}========================================${NC}"

# Показываем сводку результатов
echo -e "${YELLOW}Результаты сохранены в:${NC}"
for dir in $CREATED_DIRS; do
    if [ -d "$dir" ]; then
        echo -e "  📁 $dir"
        ls -la "$dir"/*.json 2>/dev/null | sed 's/^/    /' || echo "    (нет JSON файлов)"
    fi
done

# Инструкции по запуску Django
if [ -d "property_analyzer" ]; then
    echo ""
    echo -e "${BLUE}🌐 Для запуска веб-интерфейса:${NC}"
    echo -e "  ${GREEN}cd property_analyzer${NC}"
    echo -e "  ${GREEN}python manage.py runserver${NC}"
    echo -e "  ${GREEN}Откройте: http://127.0.0.1:8000/${NC}"
fi 