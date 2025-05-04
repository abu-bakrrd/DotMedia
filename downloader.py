import os
import re
import time
import logging
import requests
import random
import string
from urllib.parse import urlparse
import subprocess
import json
from config import MAX_RETRIES, RETRY_DELAY, REQUEST_TIMEOUT, MAX_FILE_SIZE
from utils import get_platform, extract_media_id, get_file_extension, sanitize_filename

# Заголовки для имитации браузера
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Referer': 'https://www.google.com/',
    'sec-ch-ua': '"Google Chrome";v="91", " Not;A Brand";v="99", "Chromium";v="91"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

class MediaDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def download_media(self, url, save_dir):
        """
        Скачивает медиафайл с указанного URL
        
        Args:
            url: URL медиафайла
            save_dir: Директория для сохранения
            
        Returns:
            dict: Информация о скачанном файле или None в случае ошибки
        """
        platform = get_platform(url)
        if not platform:
            logging.error(f"Неподдерживаемая платформа: {url}")
            return None
        
        try:
            if platform == 'instagram':
                return self._download_instagram(url, save_dir)
            elif platform == 'tiktok':
                return self._download_tiktok(url, save_dir)
            elif platform == 'pinterest':
                return self._download_pinterest(url, save_dir)
            else:
                logging.error(f"Неподдерживаемая платформа: {platform}")
                return None
        except Exception as e:
            logging.error(f"Ошибка при скачивании медиа: {e}")
            return None
    
    def _generate_filename(self, platform, media_id, file_type):
        """Генерирует имя файла для скачанного медиа"""
        timestamp = int(time.time())
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        extension = get_file_extension(file_type)
        filename = f"{platform}_{media_id}_{timestamp}_{random_string}{extension}"
        return sanitize_filename(filename)
    
    def _download_file(self, url, save_path):
        """Скачивает файл по URL и сохраняет по указанному пути"""
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, stream=True, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                
                # Проверяем размер файла
                content_length = int(response.headers.get('Content-Length', 0))
                if content_length > MAX_FILE_SIZE:
                    logging.warning(f"Файл слишком большой: {content_length} байт")
                    return False, "file_too_large"
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Проверяем размер скачанного файла
                file_size = os.path.getsize(save_path)
                if file_size > MAX_FILE_SIZE:
                    os.remove(save_path)
                    logging.warning(f"Скачанный файл слишком большой: {file_size} байт")
                    return False, "file_too_large"
                
                if file_size == 0:
                    os.remove(save_path)
                    logging.warning("Скачан пустой файл")
                    return False, "empty_file"
                
                return True, None
            
            except requests.exceptions.RequestException as e:
                logging.error(f"Ошибка при скачивании (попытка {attempt+1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    return False, "download_failed"
        
        return False, "max_retries"
    
    def _download_instagram(self, url, save_dir):
        """Скачивает медиафайл из Instagram"""
        media_id = extract_media_id(url, 'instagram')
        if not media_id:
            logging.error(f"Не удалось извлечь ID медиа из URL: {url}")
            return None
        
        # Используем instaloader через subprocess для скачивания
        try:
            # Генерируем временное имя для выходного файла
            output_prefix = f"instagram_{media_id}"
            output_path = os.path.join(save_dir, output_prefix)
            
            # Используем yt-dlp для скачивания (поддерживает Instagram без авторизации)
            command = [
                "yt-dlp", 
                "--no-warnings",
                "--quiet",
                "-o", f"{output_path}.%(ext)s",
                url
            ]
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            _, stderr = process.communicate()
            
            if process.returncode != 0:
                logging.error(f"Ошибка при скачивании Instagram медиа: {stderr.decode()}")
                return None
            
            # Ищем скачанный файл
            downloads = [f for f in os.listdir(save_dir) if f.startswith(output_prefix)]
            if not downloads:
                logging.error(f"Файл не найден после скачивания: {output_prefix}")
                return None
            
            file_path = os.path.join(save_dir, downloads[0])
            file_type = 'video' if file_path.endswith(('.mp4', '.mov')) else 'image'
            
            return {
                'platform': 'instagram',
                'media_id': media_id,
                'file_path': file_path,
                'file_type': file_type,
                'file_name': downloads[0]
            }
            
        except Exception as e:
            logging.error(f"Ошибка при скачивании Instagram медиа: {e}")
            return None
    
    def _download_tiktok(self, url, save_dir):
        """Скачивает медиафайл из TikTok"""
        media_id = extract_media_id(url, 'tiktok')
        if not media_id:
            logging.error(f"Не удалось извлечь ID медиа из URL: {url}")
            return None
        
        try:
            # Генерируем временное имя для выходного файла
            output_prefix = f"tiktok_{media_id}"
            output_path = os.path.join(save_dir, output_prefix)
            
            # Преобразуем короткие ссылки в полные
            if any(domain in url for domain in ['vm.tiktok.com', 'vt.tiktok.com', 'm.tiktok.com']):
                # Для коротких ссылок не нужны дополнительные параметры
                pass
            elif '/t/' in url:
                # Если это ссылка с /t/, не меняем
                pass
            else:
                # Для профильных ссылок добавляем некоторые параметры
                logging.info(f"Преобразуем URL TikTok: {url}")
            
            # Используем yt-dlp для скачивания с более подробными настройками
            command = [
                "yt-dlp", 
                "--no-warnings",
                "--user-agent", HEADERS['User-Agent'],
                "--add-header", f"Referer: {url}",
                "--add-header", "Accept-Language: ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "-o", f"{output_path}.%(ext)s",
                url
            ]
            
            logging.info(f"Скачиваем TikTok медиа: {url}")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                # Выводим ошибку с большим количеством деталей
                error_msg = stderr.decode() if stderr else 'Неизвестная ошибка'
                logging.error(f"Ошибка при скачивании TikTok медиа: {error_msg}")
                
                # Пробуем альтернативный метод скачивания
                command = [
                    "yt-dlp", 
                    "--format", "best",
                    "--no-check-certificate",
                    "-o", f"{output_path}.%(ext)s",
                    url
                ]
                
                logging.info("Пробуем альтернативный метод скачивания TikTok...")
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    # Если и этот метод не сработал, возвращаем ошибку
                    logging.error(f"Альтернативный метод скачивания TikTok также не удался")
                    return None
            
            # Ищем скачанный файл
            downloads = [f for f in os.listdir(save_dir) if f.startswith(output_prefix)]
            if not downloads:
                logging.error(f"Файл не найден после скачивания: {output_prefix}")
                return None
            
            file_path = os.path.join(save_dir, downloads[0])
            
            # Проверяем тип файла, но для TikTok в основном это видео
            file_type = 'video'
            # Если это изображение, меняем тип
            if file_path.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                file_type = 'image'
            elif file_path.endswith('.gif'):
                file_type = 'gif'
            
            logging.info(f"Успешно скачан файл TikTok: {file_path} (тип: {file_type})")
            
            return {
                'platform': 'tiktok',
                'media_id': media_id,
                'file_path': file_path,
                'file_type': file_type,
                'file_name': downloads[0]
            }
            
        except Exception as e:
            logging.error(f"Ошибка при скачивании TikTok медиа: {e}")
            return None
    
    def _download_pinterest(self, url, save_dir):
        """Скачивает медиафайл из Pinterest"""
        media_id = extract_media_id(url, 'pinterest')
        if not media_id:
            logging.error(f"Не удалось извлечь ID медиа из URL: {url}")
            return None
        
        try:
            # Генерируем временное имя для выходного файла
            output_prefix = f"pinterest_{media_id}"
            output_path = os.path.join(save_dir, output_prefix)
            
            # Сначала пробуем напрямую через Pinterest API
            try:
                # Преобразуем короткие ссылки pin.it в полные
                if 'pin.it' in url:
                    # Заменяем URL на полный формат
                    url = f"https://www.pinterest.com/pin/{media_id}/"
                
                # Получаем HTML страницы
                response = self.session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                html_content = response.text
                
                # Ищем URL изображения или видео в HTML
                # Расширенные регулярные выражения для разных форматов данных в Pinterest
                image_patterns = [
                    r'"image_url":"([^"]+)"',
                    r'"images":\{[^\}]*"orig":\{"url":"([^"]+)"',
                    r'<meta property="og:image" content="([^"]+)"',
                    r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*mainImage[^"]*"',
                    r'data-test-id="pin-image"[^>]*src="([^"]+)"'
                ]
                video_patterns = [
                    r'"video_url":"([^"]+)"',
                    r'"videos":\{[^\}]*"video_list":\{[^\}]*"url":"([^"]+)"',
                    r'<meta property="og:video" content="([^"]+)"',
                    r'<meta property="og:video:url" content="([^"]+)"'
                ]
                
                # Пробуем найти видео сначала
                for pattern in video_patterns:
                    video_match = re.search(pattern, html_content)
                    if video_match:
                        media_url = video_match.group(1).replace('\\/', '/')
                        file_type = 'video'
                        file_extension = '.mp4'
                        break
                else:
                    # Если видео не найдено, ищем изображение
                    for pattern in image_patterns:
                        image_match = re.search(pattern, html_content)
                        if image_match:
                            media_url = image_match.group(1).replace('\\/', '/')
                            file_type = 'image'
                            file_extension = '.jpg'
                            break
                    else:
                        # Если изображение не найдено, вызываем исключение
                        raise Exception("Не удалось найти URL медиа в Pinterest HTML")
                
                # Скачиваем файл
                file_name = f"{output_prefix}{file_extension}"
                file_path = os.path.join(save_dir, file_name)
                
                logging.info(f"Скачиваем Pinterest медиа: {media_url}")
                success, error = self._download_file(media_url, file_path)
                if success:
                    return {
                        'platform': 'pinterest',
                        'media_id': media_id,
                        'file_path': file_path,
                        'file_type': file_type,
                        'file_name': file_name
                    }
                logging.error(f"Ошибка при скачивании Pinterest медиа через API: {error}")
            except Exception as e:
                logging.error(f"Ошибка при использовании Pinterest API: {e}")
                # Продолжаем и пробуем через yt-dlp
            
            # Если не удалось через API, пробуем через yt-dlp
            logging.info(f"Пробуем скачать Pinterest медиа через yt-dlp: {url}")
            command = [
                "yt-dlp", 
                "--no-warnings",
                "-o", f"{output_path}.%(ext)s",
                url
            ]
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                # Если yt-dlp успешно скачал файл
                downloads = [f for f in os.listdir(save_dir) if f.startswith(output_prefix)]
                if downloads:
                    file_path = os.path.join(save_dir, downloads[0])
                    file_type = 'video' if file_path.endswith(('.mp4', '.mov')) else 'image'
                    
                    return {
                        'platform': 'pinterest',
                        'media_id': media_id,
                        'file_path': file_path,
                        'file_type': file_type,
                        'file_name': downloads[0]
                    }
            
            # Если все методы не сработали, возвращаем ошибку
            logging.error(f"Не удалось скачать Pinterest медиа: {stderr.decode() if stderr else 'Неизвестная ошибка'}")
            return None
            
        except Exception as e:
            logging.error(f"Ошибка при скачивании Pinterest медиа: {e}")
            return None
