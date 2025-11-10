import logging
from telegram import Update
from telegram.ext import Application, ContextTypes
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import asyncio

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
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ОДИН источник для чтения
SOURCE_CHAT_ID = os.getenv("SOURCE_CHAT_ID")

# Ключевые слова для фильтрации
KEYWORDS = [
    "россия", "российск", "svo", "sova", "крипт", "биткоин", "эфириум",
    "санкци", "экономик", "энергетик", "оборон", "войн", "трансферт",
    "газпром", "рубль", "нефть", "доллар", "евро", "турция", "украин", "сирия",
    "китай", "индия", "европа", "сша", "нафт", "организаци", "ооп", "нло"
]

async def check_new_messages(context: ContextTypes.DEFAULT_TYPE):
    if not SOURCE_CHAT_ID:
        logger.error("SOURCE_CHAT_ID не задан")
        return

    try:
        # Получаем последние 20 сообщений из ОДНОГО канала
        updates = await context.bot.get_chat_history(
            chat_id=int(SOURCE_CHAT_ID),
            limit=20
        )
        
        for message in updates.messages:
            if not message.text:
                continue

            title = message.text[:100].strip()  # Первые 100 символов для дедупликации
            content = message.text
            pub_date = message.date

            # Проверяем дубли за последние 7 дней
            check_time = datetime.now() - timedelta(days=7)
            check = supabase.table('news').select('id').eq('title', title).gte('pub_date', check_time.isoformat()).execute()
            if check.
                continue

            # Фильтрация по ключевым словам
            text_lower = content.lower()
            found_keywords = [kw for kw in KEYWORDS if kw in text_lower]
            if not found_keywords:
                continue

            # Сохраняем в Supabase
            supabase.table('news').insert({
                'title': title,
                'content': content,
                'source_channel': SOURCE_CHAT_ID,
                'pub_date': pub_date.isoformat(),
                'keywords': found_keywords,
                'original_message_id': message.message_id
            }).execute()

            logger.info(f"✅ Новость сохранена: {title[:50]}...")

    except Exception as e:
        logger.error(f"❌ Ошибка при чтении из {SOURCE_CHAT_ID}: {str(e)}")

def main():
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    # Запуск проверки каждые 15 минут
    job_queue = application.job_queue
    job_queue.run_repeating(check_new_messages, interval=15 * 60, first=10)

    application.run_polling()

if __name__ == '__main__':
    main()
