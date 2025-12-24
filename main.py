"""
차량사고 뉴스 텔레그램 알림 봇
- GitHub Actions용
"""

import json
from pathlib import Path
from datetime import datetime

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SEARCH_KEYWORDS,
    HIGH_PRIORITY_KEYWORDS,
)
from news_fetcher import fetch_all_news
from telegram_bot import send_news_alerts

SENT_FILE = Path(__file__).parent / "sent_news.json"


def load_sent_ids() -> set:
    if SENT_FILE.exists():
        try:
            with open(SENT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('ids', []))
        except:
            pass
    return set()


def save_sent_ids(ids: set):
    ids_list = list(ids)[-300:]
    with open(SENT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'ids': ids_list, 'updated': datetime.now().isoformat()}, f)


def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] 차량사고 뉴스 검색")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ERROR] 토큰/챗ID 없음! GitHub Secrets 확인")
        return
    
    sent_ids = load_sent_ids()
    news_items = fetch_all_news(SEARCH_KEYWORDS, HIGH_PRIORITY_KEYWORDS)
    new_count = sum(1 for n in news_items if n.news_id not in sent_ids)
    
    print(f"수집: {len(news_items)}개 / 신규: {new_count}개")
    
    if new_count > 0:
        sent_ids = send_news_alerts(
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_CHAT_ID,
            news_items,
            sent_ids
        )
        save_sent_ids(sent_ids)
    
    print("완료")


if __name__ == "__main__":
    main()
