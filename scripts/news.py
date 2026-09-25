"""보유 종목과 관련된 미국 뉴스 10개를 골라 data/news.json 에 저장한다.

- 출처: Google News RSS (미국판, 최근 1일)
- 분류: 미국 지수 5개 / 반도체 · 메모리 5개 (영문 기사, 주요 경제 매체 우선)
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


def settled(closes):
    """장이 아직 안 끝난 오늘 행(프리마켓·장중)은 빼고 확정 종가만 남긴다."""
    if closes.empty or closes.index.tz is None:
        return closes
    close_min = {"America/New_York": 16 * 60 + 10, "Asia/Seoul": 15 * 60 + 40}.get(str(closes.index.tz))
    if close_min is None:
        return closes
    now = datetime.now(closes.index.tz)
    last = closes.index[-1]
    if last.date() == now.date() and now.hour * 60 + now.minute < close_min:
        return closes.iloc[:-1]
    return closes
TOTAL = 10

# (분류, 검색어, 최대 개수, 제목에 있어야 할 단어, 제목에 함께 있어야 할 투자 관련 단어)
MARKET_WORDS = (r"stock|shares|market|earn|rall|buy|analyst|invest|price|revenue|forecast|guidance|etf|"
                r"sales|demand|valuation|\$|surge|slump|jump|fall|drop|rise|record|slide|soar|outlook|profit|export")
TOPICS = [
    ("미국 지수", '"stock market" OR "Nasdaq" OR "S&P 500" OR "Wall Street"',
     5, r"nasdaq|s&p|stock market|wall street|\bdow\b|stocks|index fund", None),
    ("반도체 · 메모리", '"chip stocks" OR semiconductor OR Micron OR "SK Hynix" OR "memory chip" OR Nvidia stock',
     5, r"chip|semiconductor|micron|hynix|hbm|dram|memory|nvidia|samsung|tsmc|broadcom|\bamd\b", MARKET_WORDS),
]

# 주요 경제 매체를 먼저, "~ 살까?" 류 칼럼은 뒤로
TIER1 = ["reuters", "bloomberg", "cnbc", "wall street journal", "wsj", "marketwatch", "barron",
         "financial times", "associated press", "ap news", "investor's business daily", "axios", "cnn"]
TIER2 = ["yahoo finance", "motley fool", "benzinga", "seeking alpha", "forbes", "business insider",
         "fortune", "thestreet", "investopedia", "morningstar", "zacks", "washington post", "new york times"]
LISTICLE = r"^prediction:|better buy|here's why|here's how|should you buy|no-brainer|to buy (right )?now|worth this much|millionaire"
SKIP = r"opening bell|closing bell|news headlines|press release"


def score(item):
    s = (item["source"] or "").lower()
    tier = 2 if any(t in s for t in TIER1) else 1 if any(t in s for t in TIER2) else 0
    return tier - (2 if re.search(LISTICLE, item["title"].lower()) else 0)


def english(title):
    letters = [c for c in title if c.isalpha()]
    return bool(letters) and sum(c.isascii() for c in letters) / len(letters) > 0.9


# 제목에 이 단어가 있으면 관련 보유 종목(holdings.json 의 id)으로 표시
HOLD = [
    (r"memory|dram|hbm|nand|micron|hynix|samsung", ["dram", "ram", "samsung"]),
    (r"semiconductor|chip|soxx|nvidia|broadcom|\bamd\b|tsmc|qualcomm", ["soxl"]),
    (r"alphabet|google", ["googl"]),
    (r"oracle", ["orcl"]),
    (r"palantir", ["pltr"]),
    (r"robinhood", ["hood"]),
    (r"lg display", ["lgdisplay"]),
    (r"nasdaq|qqq|tech stock|big tech", ["kodex-nasdaq100", "qqqm", "tqqq"]),
    (r"s&p ?500|\bdow\b|wall street|stock market", ["rise-sp500", "irp-kodex-sp500", "schd"]),
]

# 제목에 나온 종목·지수의 주가 변동 (Yahoo 심볼, 표시 이름)
SUBJECTS = [
    (r"micron", "MU", "마이크론"), (r"nvidia", "NVDA", "엔비디아"), (r"tsmc|taiwan semiconductor", "TSM", "TSMC"),
    (r"broadcom", "AVGO", "브로드컴"), (r"\bamd\b", "AMD", "AMD"), (r"qualcomm", "QCOM", "퀄컴"),
    (r"intel\b", "INTC", "인텔"), (r"asml", "ASML", "ASML"), (r"marvell", "MRVL", "마벨"),
    (r"sandisk", "SNDK", "샌디스크"), (r"applied materials", "AMAT", "어플라이드"),
    (r"hynix", "000660.KS", "SK하이닉스"), (r"samsung", "005930.KS", "삼성전자"),
    (r"alphabet|google", "GOOGL", "알파벳"), (r"oracle", "ORCL", "오라클"), (r"palantir", "PLTR", "팔란티어"),
    (r"robinhood", "HOOD", "로빈후드"), (r"apple\b", "AAPL", "애플"), (r"microsoft", "MSFT", "마이크로소프트"),
    (r"\bmeta\b", "META", "메타"), (r"amazon", "AMZN", "아마존"), (r"tesla", "TSLA", "테슬라"),
    (r"nasdaq", "^IXIC", "나스닥"), (r"s&p ?500", "^GSPC", "S&P 500"), (r"\bdow\b", "^DJI", "다우"),
]
FALLBACK = {"미국 지수": ("^GSPC", "S&P 500"), "반도체 · 메모리": ("SOXX", "반도체지수")}
_moves = {}


def price_move(symbol):
    """최근 거래일 종가 기준 등락률. 실패하면 None."""
    if symbol in _moves:
        return _moves[symbol]
    res = None
    try:
        import yfinance as yf
        c = yf.Ticker(symbol).history(period="10d", interval="1d")["Close"].dropna()
        c = settled(c)
        if len(c) >= 2:
            res = {"chgPct": round((float(c.iloc[-1]) / float(c.iloc[-2]) - 1) * 100, 2),
                   "asOf": c.index[-1].strftime("%Y-%m-%d")}
    except Exception as e:
        print(f"  ! 주가 {symbol}: {e}")
    _moves[symbol] = res
    return res


def moves(title, category):
    t = title.lower()
    found = []
    for pat, sym, name in SUBJECTS:
        if re.search(pat, t) and all(m["symbol"] != sym for m in found):
            found.append({"symbol": sym, "name": name})
        if len(found) >= 2:
            break
    if not found and category in FALLBACK:
        sym, name = FALLBACK[category]
        found.append({"symbol": sym, "name": name})
    out = []
    for m in found:
        pm = price_move(m["symbol"])
        if pm:
            out.append({**m, **pm})
    return out


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def google_news(query):
    q = urllib.parse.quote(f"{query} when:1d")
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
    ids = []
    for pat, hs in HOLD:
        if re.search(pat, t):
            ids += [h for h in hs if h not in ids]
    return ids[:3]


def main():
    now = datetime.now(KST)
    seen, picked, spare = set(), [], []
    for category, query, limit, must, ctx in TOPICS:
        try:
            items = google_news(query)
        except Exception as e:
            print(f"  ! {category} 뉴스 실패: {e}")
            continue
        def ok(it):
            t = it["title"].lower()
            return (english(it["title"]) and re.search(must, t) and not re.search(SKIP, t)
                    and (it["source"] or "").lower() != "nasdaq" and (ctx is None or re.search(ctx, t)))
        items = [it for it in items if ok(it)]
        newest = lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc)
        items.sort(key=newest, reverse=True)
        items.sort(key=score, reverse=True)  # 안정 정렬: 점수 높은 순, 같은 점수 안에서는 최신순
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
            "holdings": related(it["title"]),
            "moves": moves(it["title"], it["category"]),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updatedAt": now.isoformat(timespec="seconds"), "items": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"뉴스 {len(rows)}개 저장")


if __name__ == "__main__":
    main()
