# send_summary.py
import os
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Bot
import psycopg2

# === Конфигурация ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

if not all([BOT_TOKEN, CHANNEL_ID, SUPABASE_DB_URL]):
    raise EnvironmentError("Missing required environment variables")

bot = Bot(token=BOT_TOKEN)

# === Работа с БД ===
def get_db_connection():
    import urllib.parse as urlparse
    url = urlparse.urlparse(SUPABASE_DB_URL)
    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port,
        database=url.path[1:],
        user=url.username,
        password=url.password,
        sslmode='require'
    )
    return conn

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
        print(f"DB fetch error: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# === Генерация аналитики ===
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
        print("Daily summary sent successfully.")
    except Exception as e:
        print(f"Failed to send daily summary: {e}")

# === Запуск ===
if __name__ == "__main__":
    asyncio.run(send_daily_summary())
