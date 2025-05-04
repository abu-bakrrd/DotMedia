import logging
import os
from bot import bot

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запуск бота
    logging.info("Бот запущен")
    bot.polling(none_stop=True, interval=0)
