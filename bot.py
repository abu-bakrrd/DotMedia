import os
import logging
import telebot
import time
import threading
from telebot import types
from config import TOKEN, RATE_LIMIT
from utils import (
    is_valid_url, get_platform, rate_limit_check, 
    get_user_download_dir, create_temp_dir, cleanup_temp_files
)
from messages import (
    START_MESSAGE, HELP_MESSAGE, PROCESSING_MESSAGE, DOWNLOADING_MESSAGE, 
    SUCCESS_MESSAGE, ERROR_INVALID_URL, ERROR_UNSUPPORTED_PLATFORM, 
    ERROR_RATE_LIMIT, ERROR_DOWNLOAD_FAILED, ERROR_FILE_TOO_LARGE, 
    ERROR_GENERAL, NO_MEDIA_FOUND, MULTIPLE_MEDIA_FOUND, MEDIA_CAPTION
)
from downloader import MediaDownloader

# Инициализация бота
bot = telebot.TeleBot(TOKEN)
downloader = MediaDownloader()

# Создание временной директории при запуске
create_temp_dir()

# Словарь для отслеживания состояния пользователей
user_states = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    try:
        user_id = message.from_user.id
        bot.send_message(user_id, START_MESSAGE)
    except Exception as e:
        logging.error(f"Ошибка при отправке приветственного сообщения: {e}")

@bot.message_handler(commands=['help'])
def send_help(message):
    """Обработчик команды /help"""
    try:
        user_id = message.from_user.id
        bot.send_message(user_id, HELP_MESSAGE)
    except Exception as e:
        logging.error(f"Ошибка при отправке справки: {e}")

@bot.message_handler(func=lambda message: True)
def process_message(message):
    """Обработчик всех текстовых сообщений"""
    try:
        user_id = message.from_user.id
        text = message.text.strip()
        
        logging.info(f"Получено новое сообщение от пользователя {user_id}: {text}")
        
        # Проверяем, является ли сообщение URL
        if not is_valid_url(text):
            logging.info(f"Недействительный URL: {text}")
            bot.send_message(user_id, ERROR_INVALID_URL)
            return
        
        # Проверяем поддерживаемую платформу
        platform = get_platform(text)
        logging.info(f"Определенная платформа: {platform or 'Не определена'}")
        
        if not platform:
            logging.warning(f"Неподдерживаемая платформа: {text}")
            bot.send_message(user_id, ERROR_UNSUPPORTED_PLATFORM)
            return
        
        # Проверяем ограничение на количество запросов
        if not rate_limit_check(user_id, RATE_LIMIT):
            logging.warning(f"Превышен лимит запросов для пользователя {user_id}")
            bot.send_message(user_id, ERROR_RATE_LIMIT)
            return
        
        # Отправляем сообщение о начале обработки
        processing_msg = bot.send_message(user_id, PROCESSING_MESSAGE)
        logging.info(f"Начинаем обработку URL: {text} (платформа: {platform})")
        
        # Запускаем обработку URL в отдельном потоке
        thread = threading.Thread(
            target=process_url, 
            args=(user_id, text, processing_msg.message_id)
        )
        thread.start()
        
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")
        try:
            bot.send_message(user_id, ERROR_GENERAL)
        except:
            pass

def process_url(user_id, url, message_id):
    """Обрабатывает URL и скачивает медиафайл"""
    try:
        # Обновляем сообщение о статусе
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=DOWNLOADING_MESSAGE
        )
        
        # Создаем директорию для пользователя
        user_dir = get_user_download_dir(user_id)
        
        platform = get_platform(url)
        logging.info(f"Начинаю загрузку медиа из {platform}: {url}")
        
        # Скачиваем медиафайл
        media_info = downloader.download_media(url, user_dir)
        
        if not media_info:
            logging.warning(f"Не удалось скачать медиа с {platform}: {url}")
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=ERROR_DOWNLOAD_FAILED
            )
            return
        
        # Проверяем наличие файла
        file_path = media_info.get('file_path', '')
        if not file_path or not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            logging.warning(f"Файл не найден или пуст: {file_path}")
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=ERROR_DOWNLOAD_FAILED
            )
            return
        
        logging.info(f"Успешно скачан файл: {file_path} (тип: {media_info.get('file_type', 'unknown')})")
        
        # Отправляем скачанный файл
        send_media_file(user_id, media_info, message_id)
        
    except Exception as e:
        logging.error(f"Ошибка при обработке URL {url}: {e}")
        try:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=ERROR_GENERAL
            )
        except:
            pass

def send_media_file(user_id, media_info, message_id):
    """Отправляет медиафайл пользователю"""
    try:
        file_path = media_info['file_path']
        file_type = media_info['file_type']
        platform = media_info['platform']
        
        # К этому моменту мы уже проверили существование файла в process_url
        # Формируем подпись для медиафайла
        caption = f"{MEDIA_CAPTION} | {platform.capitalize()}"
        
        # Обновляем сообщение о статусе
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=SUCCESS_MESSAGE
        )
        
        file_size_kb = os.path.getsize(file_path) / 1024
        logging.info(f"Отправляю файл пользователю {user_id}: {file_path} (размер: {file_size_kb:.2f} КБ, тип: {file_type})")
        
        # Отправляем медиафайл в зависимости от типа
        with open(file_path, 'rb') as file:
            if file_type == 'video':
                response = bot.send_video(
                    user_id,
                    file,
                    caption=caption,
                    supports_streaming=True
                )
                logging.info(f"Видео успешно отправлено")
            elif file_type == 'image':
                response = bot.send_photo(
                    user_id,
                    file,
                    caption=caption
                )
                logging.info(f"Изображение успешно отправлено")
            elif file_type == 'gif':
                response = bot.send_animation(
                    user_id,
                    file,
                    caption=caption
                )
                logging.info(f"GIF успешно отправлен")
            else:
                # Если неизвестный тип, пробуем отправить как документ
                response = bot.send_document(
                    user_id,
                    file,
                    caption=caption
                )
                logging.info(f"Документ успешно отправлен")
        
        # Удаляем файл после отправки
        try:
            os.remove(file_path)
            logging.info(f"Файл удален: {file_path}")
        except Exception as e:
            logging.warning(f"Не удалось удалить файл: {file_path} ({e})")
        
    except telebot.apihelper.ApiException as e:
        logging.error(f"Ошибка Telegram API при отправке файла: {e}")
        if "Request Entity Too Large" in str(e):
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=ERROR_FILE_TOO_LARGE
            )
        else:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=ERROR_GENERAL
            )
    except Exception as e:
        logging.error(f"Ошибка при отправке медиафайла: {e}")
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=ERROR_GENERAL
        )

# Запускаем периодическую очистку временных файлов
def cleanup_scheduler():
    while True:
        try:
            time.sleep(3600)  # Очистка каждый час
            cleanup_temp_files()
        except Exception as e:
            logging.error(f"Ошибка при плановой очистке файлов: {e}")

# Запускаем поток очистки
cleanup_thread = threading.Thread(target=cleanup_scheduler)
cleanup_thread.daemon = True
cleanup_thread.start()
