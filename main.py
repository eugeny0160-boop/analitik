# main.py
import os
import logging
from telegram import Bot
from telegram.ext import Application, MessageHandler, filters
import psycopg2

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
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.CHANNEL_POST, handle_channel_post))
    app.run_polling()
