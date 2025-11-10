# main.py
import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.ext import Application, MessageHandler, filters
import psycopg2
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import json

# === Конфигурация ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Например: @finanosint или -1001234567890
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")  # Формат: postgresql://[user]:[password]@[host]:[port]/[database]

if not all([BOT_TOKEN, CHANNEL_ID, SUPABASE_DB_URL]):
    raise EnvironmentError("Missing required environment variables")

bot = Bot(token=BOT_TOKEN)

logging.basicConfig(level=logging.INFO)

# === Работа с БД (PostgreSQL) ===
def get_db_connection():
    import urllib.parse as urlparse
    url = urlparse.urlparse(SUPABASE_DB_URL)
    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port,
        database=url.path[1:],  # remove leading '/'
        user=url.username,
        password=url.password,
        sslmode='require'
    )
    return conn

def save_post(title: str, content: str, message_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO processed_posts (title, content, message_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (title) DO NOTHING;
        """, (title, content, message_id))
        conn.commit()
    except Exception as e:
        logging.error(f"DB insert error: {e}")
    finally:
        cur.close()
        conn.close()

def is_duplicate(title: str) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM processed_posts WHERE title = %s LIMIT 1;", (title,))
        exists = cur.fetchone() is not None
        return exists
    except Exception as e:
        logging.error(f"DB check error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_posts_since(since_dt):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT title, content, created_at
            FROM processed_posts
            WHERE created_at >= %s
            ORDER BY created_at DESC;
        """, (since_dt.isoformat(),))
        rows = cur.fetchall()
        return [{"title": r[0], "content": r[1], "created_at": r[2].isoformat()} for r in rows]
    except Exception as e:
        logging.error(f"DB fetch error: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# === Генерация аналитики (без LLM) ===
def generate_summary(period_name: str, posts: list) -> str:
    if not posts:
        return f"📊 *{period_name}*\n\nНет данных за указанный период."

    keywords = {
        "санкции": 0,
        "Россия": 0,
        "Китай": 0,
        "энергетика": 0,
        "рубль": 0,
        "Евразия": 0,
        "безопасность": 0,
        "торговля": 0,
        "технологии": 0,
    }

    full_text = " ".join([p.get("title", "") + " " + p.get("content", "") for p in posts]).lower()
    for kw in keywords:
        keywords[kw] = full_text.count(kw)

    top_topics = sorted([(k, v) for k, v in keywords.items() if v > 0], key=lambda x: x[1], reverse=True)[:5]

    text = f"📊 *{period_name}*\n\n"
    first = datetime.fromisoformat(posts[-1]["created_at"].replace("Z", "+00:00")).strftime("%d.%m.%Y")
    last = datetime.fromisoformat(posts[0]["created_at"].replace("Z", "+00:00")).strftime("%d.%m.%Y")
    text += f"Период: {first} – {last}\n"
    text += f"Уникальных постов: {len(posts)}\n\n"

    if top_topics:
        text += "Ключевые темы:\n"
        for topic, count in top_topics:
            text += f"• {topic.capitalize()} ({count})\n"
    else:
        text += "Ключевые темы не выявлены.\n"

    text += "\n— Аналитика подготовлена автоматически."
    return text

# === Отправка в канал ===
async def send_daily_summary():
    since = datetime.now(timezone.utc) - timedelta(days=1)
    posts = get_posts_since(since)
    message = generate_summary("Аналитическая записка за день", posts)
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="Markdown")
        logging.info("Daily summary sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send daily summary: {e}")

# === Обработка постов из канала ===
async def handle_channel_post(update, context):
    post = update.channel_post
    if not post or not post.text:
        return
    title = post.text.split('\n')[0][:150]
    if is_duplicate(title):
        return
    save_post(title, post.text, post.message_id)

# === Запуск ===
if __name__ == "__main__":
    # Запуск Telegram-бота
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.CHANNEL_POST, handle_channel_post))

    # Запуск задачи на отправку аналитики в 21:00 UTC каждый день
    async def schedule_daily_task():
        while True:
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)

            seconds_until_next_run = (next_run - now).total_seconds()
            logging.info(f"Next daily summary at {next_run.strftime('%H:%M:%S')} UTC. Waiting {seconds_until_next_run:.0f} seconds.")

            await asyncio.sleep(seconds_until_next_run)
            await send_daily_summary()

    # Запуск бота и планировщика в фоне
    loop = asyncio.get_event_loop()
    loop.create_task(app.run_polling())
    loop.create_task(schedule_daily_task())

    loop.run_forever()
