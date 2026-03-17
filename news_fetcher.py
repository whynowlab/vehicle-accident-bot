import feedparser
import requests
from urllib.parse import quote
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict
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
    google_link: str = ""


@dataclass
class NewsGroup:
    """같은 사건으로 묶인 뉴스 그룹"""
    representative: NewsItem
    related: List[NewsItem] = field(default_factory=list)
    search_query: str = ""

    @property
    def total_count(self) -> int:
        return 1 + len(self.related)

    @property
    def sources(self) -> str:
        all_sources = [self.representative.source] + [r.source for r in self.related]
        unique = list(dict.fromkeys(s for s in all_sources if s))
        return ", ".join(unique[:3])

    @property
    def priority(self) -> str:
        if self.representative.priority == "HIGH":
            return "HIGH"
        if any(r.priority == "HIGH" for r in self.related):
            return "HIGH"
        return "NORMAL"

    @property
    def google_search_url(self) -> str:
        q = self.search_query or self.representative.title.split(' - ')[0][:30]
        return f"https://news.google.com/search?q={quote(q)}+when:1d&hl=ko&gl=KR&ceid=KR:ko"


def generate_news_id(title: str, link: str) -> str:
    content = f"{title}_{link}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def get_real_url(google_url: str) -> str:
    """Google News 링크를 실제 뉴스 사이트 링크로 변환"""
    try:
        response = requests.head(google_url, allow_redirects=True, timeout=5)
        return response.url
    except Exception:
        return google_url


def check_priority(text: str, high_keywords: List[str]) -> str:
    for keyword in high_keywords:
        if keyword in text:
            return "HIGH"
    return "NORMAL"


LOCATIONS = re.compile(
    r'(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주'
    r'|용인|김제|파주|제천|성남|수원|화성|고양|남양주|안산|안양|평택|의정부|시흥|포천'
    r'|연천|의성|양구|여의도|성수동|양평|청주|천안|전주|포항|창원|춘천'
    r'|강릉|원주|충주|구미|김해|양산|거제|통영|목포|여수|순천|군산|익산|제천|영주'
    r'|동대문|강남|서초|마포|종로|영등포|송파|관악|구로|노원|도봉|은평|강서|강동|성북|중구)'
)

ACCIDENT_TYPES = re.compile(r'(돌진|추돌|충돌|전복|역주행|음주운전|뺑소니|질주|폭주|급발진)')
TARGETS = re.compile(r'(상가|건물|인도|학교|어린이집|스쿨버스|통학|화물차|트럭|승용차|버스|오토바이|택시|SUV|보행자|행인|보도)')


def extract_keywords(title: str) -> set:
    """제목에서 핵심 키워드 추출 (중복 체크용)"""
    locations = LOCATIONS.findall(title)
    accident_types = ACCIDENT_TYPES.findall(title)
    targets = TARGETS.findall(title)
    return set(locations + accident_types + targets)


def extract_core_incident(title: str) -> str:
    """사건의 핵심을 추출 (그룹핑용)"""
    clean = title.split(' - ')[0].strip()
    locs = LOCATIONS.findall(clean)
    types = ACCIDENT_TYPES.findall(clean)
    loc = locs[0] if locs else ""
    atype = types[0] if types else ""
    return f"{loc}_{atype}" if loc or atype else ""


def is_similar(title_a: str, title_b: str) -> bool:
    """두 제목이 같은 사건인지 판단"""
    kw_a = extract_keywords(title_a)
    kw_b = extract_keywords(title_b)

    if len(kw_a) < 2 or len(kw_b) < 2:
        return False

    common = kw_a & kw_b
    # 키워드 2개 이상 겹치면 같은 사건으로 판단 (기존 3개 → 2개로 낮춤)
    if len(common) >= 2:
        return True

    # 핵심 사건 동일하면 같은 사건
    core_a = extract_core_incident(title_a)
    core_b = extract_core_incident(title_b)
    if core_a and core_b and core_a == core_b:
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
            link = get_real_url(google_link)
            published = entry.get('published', '')[:16] if entry.get('published') else datetime.now().strftime("%Y-%m-%d")
            source = entry.get('source', {}).get('title', '')

            # 관련성 체크
            if not any(k in title for k in ['차량', '사고', '돌진', '추돌', '충돌', '운전', '트럭', '버스', '승용차', '질주', '폭주', '급발진']):
                continue

            # 해외 뉴스 제외
            if any(k in title for k in ['美', '미국', '중국', '日', '일본', '네덜란드', '독일', '영국', '대만', '호주']):
                continue

            priority = check_priority(title, high_keywords)
            news_id = generate_news_id(title, link)

            items.append(NewsItem(
                title=title,
                link=link,
                source=source,
                published=published,
                priority=priority,
                news_id=news_id,
                google_link=google_link,
            ))

    except Exception as e:
        print(f"[ERROR] Google News: {e}")

    return items


def group_news(items: List[NewsItem]) -> List[NewsGroup]:
    """같은 사건의 뉴스를 그룹핑"""
    groups: List[NewsGroup] = []

    for item in items:
        matched_group = None
        for group in groups:
            if is_similar(item.title, group.representative.title):
                matched_group = group
                break
            for related in group.related:
                if is_similar(item.title, related.title):
                    matched_group = group
                    break
            if matched_group:
                break

        if matched_group:
            matched_group.related.append(item)
        else:
            # 검색 쿼리 생성
            clean_title = item.title.split(' - ')[0].strip()
            locs = LOCATIONS.findall(clean_title)
            types = ACCIDENT_TYPES.findall(clean_title)
            query_parts = []
            if locs:
                query_parts.append(locs[0])
            query_parts.append("차량")
            if types:
                query_parts.append(types[0])
            else:
                query_parts.append("사고")

            groups.append(NewsGroup(
                representative=item,
                search_query=" ".join(query_parts),
            ))

    return groups


def fetch_all_news(keywords: List[str], high_keywords: List[str]) -> List[NewsGroup]:
    """뉴스 수집 + 중복 그룹핑"""
    all_items = []
    seen_ids = set()

    for keyword in keywords:
        for item in fetch_google_news(keyword, high_keywords):
            if item.news_id not in seen_ids:
                seen_ids.add(item.news_id)
                all_items.append(item)
        time.sleep(0.3)

    # 그룹핑
    groups = group_news(all_items)

    # HIGH 우선 정렬, 기사 많은 순 2차 정렬
    groups.sort(key=lambda g: (0 if g.priority == "HIGH" else 1, -g.total_count))

    return groups
