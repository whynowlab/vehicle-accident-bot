import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
import hashlib
import time
import re


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: Optional[str]
    priority: str
    news_id: str


def generate_news_id(title: str, link: str) -> str:
    content = f"{title}_{link}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def get_real_url(google_url: str) -> str:
    """Google News 링크를 실제 뉴스 사이트 링크로 변환"""
    try:
        response = requests.head(google_url, allow_redirects=True, timeout=5)
        return response.url
    except:
        return google_url


def check_priority(text: str, high_keywords: List[str]) -> str:
    for keyword in high_keywords:
        if keyword in text:
            return "HIGH"
    return "NORMAL"


def extract_keywords(title: str) -> set:
    """제목에서 핵심 키워드 추출 (중복 체크용)"""
    locations = re.findall(r'(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주|용인|김제|파주|제천|성남|수원|화성|고양|남양주|안산|안양|평택|의정부|시흥|포천|연천|의성|양구|여의도|성수동|양평|청주|천안|전주|포항|창원|춘천)', title)
    accident_types = re.findall(r'(돌진|추돌|충돌|전복|역주행|음주운전|뺑소니)', title)
    targets = re.findall(r'(상가|건물|인도|학교|어린이집|스쿨버스|통학|화물차|트럭|승용차|버스|오토바이)', title)
    return set(locations + accident_types + targets)


def is_duplicate(new_title: str, existing_titles: List[str], threshold: int = 3) -> bool:
    """키워드 3개 이상 겹치면 중복으로 판단"""
    new_keywords = extract_keywords(new_title)
    if len(new_keywords) < 2:
        return False
    
    for existing in existing_titles:
        existing_keywords = extract_keywords(existing)
        common = new_keywords & existing_keywords
        if len(common) >= threshold:
            return True
    return False


def fetch_google_news(keyword: str, high_keywords: List[str]) -> List[NewsItem]:
    items = []
    try:
        encoded = quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded}+when:1d&hl=ko&gl=KR&ceid=KR:ko"
        
        feed = feedparser.parse(url)
        
        for entry in feed.entries[:8]:
            title = entry.get('title', '')
            google_link = entry.get('link', '')
            link = get_real_url(google_link)  # 실제 링크로 변환
            published = entry.get('published', '')[:16] if entry.get('published') else datetime.now().strftime("%Y-%m-%d")
            source = entry.get('source', {}).get('title', '')
            
            # 관련성 체크
            if not any(k in title for k in ['차량', '사고', '돌진', '추돌', '충돌', '운전', '트럭', '버스', '승용차']):
                continue
            
            # 해외 뉴스 제외
            if any(k in title for k in ['美', '미국', '중국', '日', '일본', '네덜란드', '독일', '영국']):
                continue
            
            priority = check_priority(title, high_keywords)
            news_id = generate_news_id(title, link)
            
            items.append(NewsItem(
                title=title,
                link=link,
                source=source,
                published=published,
                priority=priority,
                news_id=news_id
            ))
            
    except Exception as e:
        print(f"[ERROR] Google News: {e}")
    
    return items


def fetch_all_news(keywords: List[str], high_keywords: List[str]) -> List[NewsItem]:
    """뉴스 수집 + 중복 제거"""
    all_items = []
    seen_ids = set()
    seen_titles = []
    
    for keyword in keywords:
        for item in fetch_google_news(keyword, high_keywords):
            if item.news_id not in seen_ids and not is_duplicate(item.title, seen_titles):
                seen_ids.add(item.news_id)
                seen_titles.append(item.title)
                all_items.append(item)
        time.sleep(0.3)
    
    # HIGH 우선 정렬
    all_items.sort(key=lambda x: (0 if x.priority == "HIGH" else 1))
    
    return all_items
