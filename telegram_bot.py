import requests
from typing import List, Set
from news_fetcher import NewsItem


def send_telegram_message(token: str, chat_id: str, message: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")
        return False


def format_news_message(item: NewsItem) -> str:
    emoji = "🚨" if item.priority == "HIGH" else "🚗"
    date = item.published[:10] if item.published and len(item.published) >= 10 else ""
    title = item.title.split(' - ')[0] if ' - ' in item.title else item.title
    
    return f"{emoji} {date}\n{title}\n{item.source}\n{item.link}"


def send_news_alerts(token: str, chat_id: str, items: List[NewsItem], sent_ids: Set[str]) -> Set[str]:
    new_sent_ids = set()
    
    for item in items:
        if item.news_id in sent_ids:
            continue
        
        message = format_news_message(item)
        
        if send_telegram_message(token, chat_id, message):
            new_sent_ids.add(item.news_id)
            mark = "🚨" if item.priority == "HIGH" else "📰"
            print(f"[SENT] {mark} {item.title[:40]}...")
    
    return sent_ids | new_sent_ids
