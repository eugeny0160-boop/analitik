import os
from supabase import create_client, Client
from datetime import datetime, timedelta
import json
from analyze_template import build_summary

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ANALYSIS_CHAT_IDS = json.loads(os.getenv("ANALYSIS_CHAT_IDS", "[]"))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_news_for_period(period_hours):
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=period_hours)
    response = supabase.table('news').select('*').gte('pub_date', start_time.isoformat()).lt('pub_date', end_time.isoformat()).eq('processed', False).execute()
    return response.data

def send_to_telegram(chat_id, text):
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ Ошибка отправки в {chat_id}: {str(e)}")
        return None

def run_analysis():
    periods = {
        'сутки': 24,
        'неделя': 24 * 7,
        'месяц': 24 * 30,
        '6 месяцев': 24 * 180,
        'год': 24 * 365
    }

    for period_name, period_hours in periods.items():
        news = get_news_for_period(period_hours)
        if not news:
            continue

        # Формируем аналитику
        all_texts = [item['content'] for item in news]
        urls = [f"[{item['source_channel']}]({item['source_channel']})" for item in news]
        summary = build_summary(all_texts, urls, period_name)

        # Отправляем В ДВА КАНАЛА
        for chat_id in ANALYSIS_CHAT_IDS:
            result = send_to_telegram(int(chat_id), summary)
            if result and result.get('ok'):
                print(f"✅ Аналитика за {period_name} отправлена в {chat_id}")
            else:
                print(f"❌ Не удалось отправить в {chat_id}")

        # Помечаем новости как обработанные
        ids = [item['id'] for item in news]
        supabase.table('news').update({'processed': True}).in_('id', ids).execute()

if __name__ == '__main__':
    run_analysis()
