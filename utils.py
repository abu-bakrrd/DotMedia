import os
import re
import time
import logging
import shutil
from urllib.parse import urlparse, ParseResult
from config import SUPPORTED_PLATFORMS, TEMP_DIR

# Словарь для отслеживания последних запросов пользователей
user_requests = {}

def create_temp_dir():
    """Создает временную директорию, если она не существует"""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

def cleanup_temp_files():
    """Удаляет старые временные файлы"""
    try:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
            create_temp_dir()
    except Exception as e:
        logging.error(f"Ошибка при очистке временных файлов: {e}")

def get_user_download_dir(user_id):
    """Создает и возвращает путь к директории для загрузок пользователя"""
    user_dir = os.path.join(TEMP_DIR, str(user_id))
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

def is_valid_url(url):
    """Проверяет, является ли строка корректным URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_platform(url):
    """Определяет платформу по URL"""
    if not is_valid_url(url):
        return None
    
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    for platform, domains in SUPPORTED_PLATFORMS.items():
        # Проверяем точное совпадение домена
        if any(domain == d for d in domains):
            return platform
        # Проверяем, содержится ли один из доменов платформы в URL
        if any(d in domain for d in domains):
            return platform
    
    return None

def extract_media_id(url, platform):
    """Извлекает идентификатор медиа из URL в зависимости от платформы"""
    parsed_url: ParseResult = urlparse(url)
    
    if platform == 'instagram':
        # Instagram URL patterns:
        # https://www.instagram.com/p/{shortcode}/
        # https://www.instagram.com/reel/{shortcode}/
        match = re.search(r'/(p|reel|tv)/([^/]+)', parsed_url.path)
        return match.group(2) if match else None
    
    elif platform == 'tiktok':
        # TikTok URL patterns:
        # https://www.tiktok.com/@username/video/{id}
        # https://vm.tiktok.com/{shortcode}/
        # https://vt.tiktok.com/{shortcode}/
        # https://www.tiktok.com/t/{shortcode}/
        if parsed_url.netloc in ['vm.tiktok.com', 'm.tiktok.com', 'vt.tiktok.com']:
            return parsed_url.path.strip('/')
        elif '/t/' in parsed_url.path:
            # Формат /t/{code}/
            match = re.search(r'/t/([^/]+)', parsed_url.path)
            return match.group(1) if match else None
        elif '@' in parsed_url.path and '/video/' in parsed_url.path:
            # Формат /@username/video/{id}
            match = re.search(r'/video/(\d+)', parsed_url.path)
            return match.group(1) if match else None
        else:
            # Пытаемся найти любой идентификатор в пути
            parts = [p for p in parsed_url.path.split('/') if p and p != 't']
            return parts[-1] if parts else None
    
    elif platform == 'pinterest':
        # Pinterest URL patterns:
        # https://www.pinterest.com/pin/{id}/
        # https://pin.it/{shortcode}
        if parsed_url.netloc == 'pin.it':
            return parsed_url.path.strip('/')
        else:
            match = re.search(r'/pin/([^/]+)', parsed_url.path)
            return match.group(1) if match else None
    
    return None

def rate_limit_check(user_id, limit=5, period=60):
    """
    Проверяет ограничение на количество запросов от пользователя
    
    Args:
        user_id: Идентификатор пользователя
        limit: Максимальное количество запросов за период
        period: Период в секундах
    
    Returns:
        bool: True, если лимит не превышен, False в противном случае
    """
    current_time = time.time()
    
    if user_id not in user_requests:
        user_requests[user_id] = []
    
    # Удаляем устаревшие запросы
    user_requests[user_id] = [t for t in user_requests[user_id] if current_time - t < period]
    
    # Проверяем лимит
    if len(user_requests[user_id]) >= limit:
        return False
    
    # Добавляем текущий запрос
    user_requests[user_id].append(current_time)
    return True

def get_file_extension(file_type):
    """Возвращает расширение файла в зависимости от его типа"""
    extensions = {
        'video': '.mp4',
        'image': '.jpg',
        'gif': '.gif'
    }
    return extensions.get(file_type, '.unknown')

def sanitize_filename(filename):
    """Очищает имя файла от недопустимых символов"""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)
