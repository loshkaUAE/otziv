"""
Конфигурация Telegram бота для заработка на отзывах.
Автоматически загружает переменные из .env файла при локальной разработке.
На продакшене (Bothost.RU) использует переменные окружения системы.
"""

import os
from pathlib import Path

# ===== АВТОМАТИЧЕСКАЯ ЗАГРУЗКА .env ФАЙЛА =====
def load_env_file():
    """Пытается загрузить переменные из .env файла для локальной разработки."""
    try:
        from dotenv import load_dotenv

        # Ищем .env файл в текущей директории
        env_path = Path('.') / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            print("✅ .env файл загружен")
            return True
        else:
            print("ℹ️ .env файл не найден, используем системные переменные окружения")
            return False
    except ImportError:
        print("ℹ️ python-dotenv не установлен, используем системные переменные окружения")
        return False

# Пытаемся загрузить .env файл
load_env_file()

# ===== ОСНОВНЫЕ НАСТРОЙКИ БОТА =====
# Токен бота от @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID администраторов через запятую (например: "123456789,987654321")
admin_ids_str = os.getenv('ADMIN_IDS', '')
if admin_ids_str:
    ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip().isdigit()]
else:
    ADMIN_IDS = []

# ===== ЦЕНЫ ЗА ОТЗЫВЫ =====
PRICES = {
    'yandex': 50,   # Яндекс Карты
    '2gis': 50,     # 2ГИС
    'other': 30     # Другие платформы
}

# ===== НАСТРОЙКИ ВЫВОДА =====
MIN_WITHDRAW = 100  # Минимальная сумма для вывода (рублей)

# ===== РЕФЕРАЛЬНАЯ СИСТЕМА =====
REFERRAL_PERCENTS = {
    'level1': 10,  # 10% за реферала 1 уровня
    'level2': 5    # 5% за реферала 2 уровня
}

# ===== КУЛДАУН ЗАДАНИЙ =====
TASK_COOLDOWN_HOURS = 48  # Время скрытия задания после выполнения (в часах)

# ===== ССЫЛКИ =====
SUPPORT_USERNAME = "@JoelRathod"
NEWS_CHANNEL = "https://t.me/otziv828"

# ===== ПУТИ К ФАЙЛАМ =====
DB_PATH = 'data.db'
SCREENSHOTS_DIR = 'screenshots'

# ===== ПРОВЕРКА КОНФИГУРАЦИИ =====
def check_config():
    """Проверяет обязательные настройки. Вызывается вручную из main.py."""
    errors = []
    warnings = []

    # Критические ошибки
    if not BOT_TOKEN:
        errors.append("❌ BOT_TOKEN не задан. Создайте .env файл или задайте переменную окружения.")

    # Предупреждения
    if not ADMIN_IDS:
        warnings.append("⚠️ ADMIN_IDS не заданы. Бот будет работать без администраторов.")

    if not all(key in PRICES for key in ['yandex', '2gis', 'other']):
        warnings.append("⚠️ В PRICES отсутствуют некоторые ключи.")

    # Вывод результатов
    if errors:
        print("\n".join(errors))
        print("\n📋 ИНСТРУКЦИЯ:")
        print("1. Создайте в папке проекта файл .env")
        print("2. Добавьте в него строки:")
        print("   BOT_TOKEN=ваш_токен_от_BotFather")
        print("   ADMIN_IDS=8128597782,984978358")
        print("3. Убедитесь, что установлен python-dotenv: pip install python-dotenv")
        raise ValueError("Критическая ошибка конфигурации")

    if warnings:
        print("\n".join(warnings))

    print("✅ Конфигурация загружена успешно!")
    print(f"   Администраторов: {len(ADMIN_IDS)}")
    print(f"   Токен: {'Установлен' if BOT_TOKEN else 'ОТСУТСТВУЕТ'}")

    return True

# Конфигурация НЕ проверяется автоматически при импорте
# Проверку нужно вызвать вручную из main.py