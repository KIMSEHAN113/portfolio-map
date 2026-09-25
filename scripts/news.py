"""보유 종목과 관련된 미국 뉴스 10개를 골라 data/news.json 에 저장한다.

- 출처: Google News RSS (미국판, 최근 2일)
- 분류: 미국 지수 5개 / 반도체 · 메모리 5개 (영문 기사, 신뢰 매체 우선)
- 제목은 한국어로 번역해 한 줄 요약으로 쓰고, 원문 제목과 링크를 함께 저장한다.
- 실패해도 기존 news.json 을 지우지 않는다.
"""
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "news.json"
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (portfolio-map news)"}
TOTAL = 10

# (분류, 검색어, 최대 개수, 제목에 반드시 있어야 할 단어)
TOPICS = [
    ("미국 지수",
     'intitle:"Nasdaq" OR intitle:"S&P 500" OR intitle:"stock market" OR intitle:"Wall Street" OR intitle:"stocks"',
     5, r"nasdaq|s&p|stock market|wall street|stocks|dow|index fund|etf|fed\b"),
    ("반도체 · 메모리",
     'intitle:chip OR intitle:chips OR intitle:semiconductor OR intitle:Micron OR intitle:"SK Hynix" OR intitle:HBM OR intitle:DRAM OR intitle:Nvidia',
     5, r"chip|semiconductor|micron|hynix|hbm|dram|memory|nvidia|samsung|tsmc|broadcom"),
]

# 신뢰할 만한 매체를 먼저 고른다 (없으면 최신순)
TRUSTED = ["reuters", "bloomberg", "cnbc", "wall street journal", "wsj", "marketwatch", "barron",
           "yahoo finance", "investor's business daily", "financial times", "associated press", "ap news",
           "the motley fool", "motley fool", "benzinga", "seeking alpha", "forbes", "business insider",
           "fortune", "thestreet", "investopedia", "morningstar", "zacks", "nasdaq", "cnn business", "axios"]


def trusted(source):
    s = (source or "").lower()
    return any(t in s for t in TRUSTED)


def english(title):
    letters = [c for c in title if c.isalpha()]
    return bool(letters) and sum(c.isascii() for c in letters) / len(letters) > 0.9


# 제목에 이 단어가 있으면 관련 보유 종목으로 표시
RELATED = [
    (r"memory|dram|hbm|nand|micron|hynix|samsung", "DRAM · RAM · 삼성전자"),
    (r"semiconductor|chip|soxx|nvidia|broadcom|\bamd\b|tsmc", "SOXL"),
    (r"alphabet|google", "GOOGL"),
    (r"oracle", "ORCL"),
    (r"palantir", "PLTR"),
    (r"robinhood", "HOOD"),
    (r"lg display", "LGD"),
    (r"nasdaq|qqq|tech stocks|big tech", "KODEX 나스닥100 · QQQM · TQQQ · QLD"),
    (r"s&p ?500|\bdow\b|wall street", "RISE·KODEX S&P500 · SCHD"),
    (r"dividend", "SCHD"),
    (r"treasury|bond yield|\bfed\b|federal reserve|rate cut", "나스닥100미국채50"),
]


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def google_news(query):
    q = urllib.parse.quote(f"{query} when:2d")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    root = ET.fromstring(fetch(url))
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        try:
            published = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            published = None
        if title and link:
            items.append({"title": title, "link": link, "source": source, "published": published})
    return items


def translate_ko(text):
    """무료 번역 엔드포인트. 실패하면 None."""
    try:
        q = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ko&dt=t&q={q}"
        data = json.loads(fetch(url, timeout=10).decode("utf-8"))
        out = "".join(seg[0] for seg in data[0] if seg and seg[0])
        return out.strip() or None
    except Exception as e:
        print(f"  ! 번역 실패: {e}")
        return None


def norm(title):
    return re.sub(r"[^a-z0-9 ]", "", title.lower())[:60]


def related(title):
    t = title.lower()
    tags = []
    for pat, name in RELATED:
        if re.search(pat, t) and name not in tags:
            tags.append(name)
    return tags[:2]


def main():
    now = datetime.now(KST)
    seen, picked, spare = set(), [], []
    for category, query, limit, must in TOPICS:
        try:
            items = google_news(query)
        except Exception as e:
            print(f"  ! {category} 뉴스 실패: {e}")
            continue
        items = [it for it in items if english(it["title"]) and re.search(must, it["title"].lower())]
        newest = lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc)
        items.sort(key=newest, reverse=True)
        items.sort(key=lambda x: trusted(x["source"]), reverse=True)  # 안정 정렬: 신뢰 매체 우선, 그 안에서 최신순
        n = 0
        for it in items:
            key = norm(it["title"])
            if key in seen:
                continue
            seen.add(key)
            it["category"] = category
            if n < limit:
                picked.append(it)
                n += 1
            else:
                spare.append(it)
        if n:
            picked[-n:] = sorted(picked[-n:], key=newest, reverse=True)

    spare.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    picked += spare[: max(0, TOTAL - len(picked))]
    picked = picked[:TOTAL]
    if not picked:
        print("뉴스를 하나도 받지 못해 기존 파일을 유지합니다.")
        return

    rows = []
    for it in picked:
        pub = it["published"].astimezone(KST) if it["published"] else None
        rows.append({
            "category": it["category"],
            "summary": translate_ko(it["title"]) or it["title"],
            "title": it["title"],
            "source": it["source"],
            "link": it["link"],
            "published": pub.isoformat(timespec="minutes") if pub else None,
            "related": related(it["title"]),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updatedAt": now.isoformat(timespec="seconds"), "items": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"뉴스 {len(rows)}개 저장")


if __name__ == "__main__":
    main()
