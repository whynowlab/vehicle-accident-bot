import requests
from typing import List, Set
from news_fetcher import NewsGroup


def send_telegram_message(token: str, chat_id: str, message: str, parse_mode: str = "HTML") -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            print(f"[ERROR] Telegram API: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")
        return False


def format_group_message(group: NewsGroup) -> str:
    """그룹화된 뉴스를 포맷"""
    item = group.representative
    emoji = "🚨" if group.priority == "HIGH" else "🚗"
    priority_tag = " <b>HIGH</b>" if group.priority == "HIGH" else ""

    # 제목에서 언론사 제거 (보통 " - 언론사" 형식)
    title = item.title.split(' - ')[0].strip() if ' - ' in item.title else item.title
    date = item.published[:10] if item.published and len(item.published) >= 10 else ""

    # 출처 (여러 건이면 "외 N건")
    source_text = item.source or "뉴스"
    if group.total_count > 1:
        source_text += f" 외 {group.total_count - 1}건"

    lines = [
        f"{emoji}{priority_tag} {date}",
        f"<b>{title}</b>",
        f"",
        f"📰 {source_text}",
        f'🔗 <a href="{item.link}">기사 원문</a>',
        f'🔍 <a href="{group.google_search_url}">관련 뉴스 더보기</a>',
    ]

    return "\n".join(lines)


def send_news_alerts(token: str, chat_id: str, groups: List[NewsGroup], sent_ids: Set[str]) -> Set[str]:
    new_sent_ids = set()
    new_groups = [g for g in groups if g.representative.news_id not in sent_ids]

    if not new_groups:
        print("[DEBUG] 신규 뉴스 없음")
        return sent_ids

    print(f"[DEBUG] 전송 시작: {len(new_groups)}개 사건")

    # 일괄 메시지 구성 (최대 10건씩 묶어서)
    batch_size = 10
    for i in range(0, len(new_groups), batch_size):
        batch = new_groups[i:i + batch_size]

        parts = []
        for group in batch:
            parts.append(format_group_message(group))
            # 그룹 내 모든 기사 ID를 sent로 기록
            new_sent_ids.add(group.representative.news_id)
            for related in group.related:
                new_sent_ids.add(related.news_id)

        message = "\n━━━━━━━━━━\n".join(parts)

        if send_telegram_message(token, chat_id, message):
            for group in batch:
                mark = "🚨" if group.priority == "HIGH" else "📰"
                print(f"[SENT] {mark} {group.representative.title[:40]}... ({group.total_count}건)")
        else:
            # HTML 파싱 실패 시 plain text fallback
            plain = message.replace("<b>", "").replace("</b>", "")
            plain = plain.replace('<a href="', '').replace('">', ' ').replace("</a>", "")
            send_telegram_message(token, chat_id, plain, parse_mode="")

    print(f"[DEBUG] 전송 완료: {len(new_sent_ids)}개 기사 처리 ({len(new_groups)}개 사건)")

    return sent_ids | new_sent_ids
