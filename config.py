import os

# Telegram Bot API токен
TOKEN = '7941732919:AAHtDbkfbcsat4q2Kgum2KeZVFRbSYNxXes'

# Максимальное количество скачиваний в минуту для одного пользователя
RATE_LIMIT = 5

# Максимальный размер файла для отправки (в байтах)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Папка для временных файлов
TEMP_DIR = "downloads"

# Время жизни временных файлов (в секундах)
TEMP_FILE_TTL = 3600  # 1 час

# Поддерживаемые платформы и их домены
SUPPORTED_PLATFORMS = {
    "instagram": ["instagram.com", "www.instagram.com", "instagr.am"],
    "tiktok": ["tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com", "m.tiktok.com"]
}

# Таймаут для HTTP запросов (в секундах)
REQUEST_TIMEOUT = 30

# Максимальное количество попыток скачивания
MAX_RETRIES = 3

# Задержка между попытками (в секундах)
RETRY_DELAY = 2
