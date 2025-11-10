import logging
from telegram import Update
from telegram.ext import Application, ContextTypes
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import re

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Подключение к Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Каналы, откуда читаем
SOURCE_CHAT_IDS = json.loads(os.getenv("SOURCE_CHAT_IDS", "[]"))

# Ключевые слова для фильтрации
KEYWORDS = [
    "россия", "российск", "svo", "sova", "крипт", "биткоин", "эфириум",
    "санкци", "экономик", "энергетик", "оборон", "войн", "трансферт",
    "газпром", "рубль", "нефть", "доллар", "евро", "турция", "украин", "сирия",
    "китай", "индия", "европа", "сша", "нафт", "организаци", "ооп", "нло"
]

async def check_new_messages(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in SOURCE_CHAT_IDS:
        try:
            # Получаем последние 10 сообщений (можно увеличить)
            updates = await context.bot.get_chat_history(chat_id=chat_id, limit=10)
            for message in updates.messages:
                if not message.text:
                    continue

                title = message.text[:100].strip()  # Первые 100 символов — для дедупликации
                content = message.text
                pub_date = message.date

                # Проверяем дубль по заголовку
                response = supabase.table('news').select('*').eq('title', title).execute()
                if response.data:
                    continue  # Пропускаем дубль

                # Проверяем, содержит ли текст ключевые слова
                text_lower = content.lower()
                found_keywords = [kw for kw in KEYWORDS if kw in text_lower]
                if not found_keywords:
                    continue  # Не содержит нужных слов — пропускаем

                # Сохраняем в Supabase
                supabase.table('news').insert({
                    'title': title,
                    'content': content,
                    'source_channel': str(chat_id),
                    'pub_date': pub_date.isoformat(),
                    'keywords': found_keywords,
                    'original_message_id': message.message_id
                }).execute()

                logger.info(f"Сообщение сохранено: {title[:50]}...")

        except Exception as e:
            logger.error(f"Ошибка при чтении из чата {chat_id}: {e}")

def main():
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    # Запуск проверки каждые 15 минут
    job_queue = application.job_queue
    job_queue.run_repeating(check_new_messages, interval=15 * 60, first=10)

    application.run_polling()

if __name__ == '__main__':
    main()
