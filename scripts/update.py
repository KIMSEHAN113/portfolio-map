"""매일 보유 종목의 종가와 USD/KRW 환율을 받아 data/history.json 에 하루치 기록을 추가한다.

GitHub Actions 에서 매일 오전 6시(한국시간)에 실행된다.
- 수량은 holdings.json 의 qty 를 고치면 된다.
- dca(적립식) 가 있는 종목은 since 이후 지정 요일마다 shares 만큼 수량이 자동으로 늘어난다.
- 국내 종목은 네이버 증권, 해외 종목과 환율은 Yahoo Finance 차트 API 에서 받는다. 실패하면 서로를 예비로 쓴다.
- 로직 점검: python scripts/update.py --selftest
"""
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
HOLDINGS = ROOT / "holdings.json"
HISTORY = ROOT / "data" / "history.json"
KST = timezone(timedelta(hours=9))
MAX_SNAPSHOTS = 900
WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4}
UA = {"User-Agent": "Mozilla/5.0 (portfolio-map)"}
# 실행 요일(월=0)별로 "정상적인" 최근 영업일까지의 최대 날짜 차이. 이보다 크면
# 주말 때문이 아니라 시세 공급처(Yahoo/네이버)가 아직 전날 종가를 반영 못 한 것.
EXPECTED_GAP = {0: 3, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 2}


def is_delayed(as_of, today):
    """공휴일은 고려하지 않는 단순 요일 기준 판정. (ponytail: 공휴일 캘린더 없음)"""
    if not as_of:
        return False
    gap = (today - date.fromisoformat(as_of)).days
    return gap > EXPECTED_GAP[today.weekday()]


CLOSE_MIN = {"America/New_York": 16 * 60 + 10, "Asia/Seoul": 15 * 60 + 40}  # 정규장 마감(+여유) 시각


def settled_closes(bars, last_day, last_price, now, close_min):
    """일봉 {날짜: 종가} 에서 확정 종가만 날짜순으로 돌려준다.

    Yahoo 일봉에는 방금 끝난 거래일이 빠지는 일이 잦아서(브리핑이 하루 밀리던 원인),
    마지막 체결일(last_day)의 정규장이 끝났으면 meta 의 최종 체결가로 채우고,
    아직 장중·프리마켓이면 그날 값은 뺀다. close_min 이 없으면(환율 등) 마지막 값을 그대로 쓴다.
    """
    done = close_min is None or last_day < now.date() or now.hour * 60 + now.minute >= close_min
    bars = {d: c for d, c in bars.items() if d < last_day}
    if done:
        bars[last_day] = last_price
    return sorted(bars.items())


def num(v):
    return float(str(v).replace(",", "").replace("%", "").strip())


def naver_quote(code):
    """네이버 증권 국내 종목 시세: (종가, 등락률%, 날짜)."""
    try:
        req = urllib.request.Request(f"https://m.stock.naver.com/api/stock/{code}/basic", headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
        price = num(j["closePrice"])
        chg = num(j.get("fluctuationsRatio", 0))
        as_of = str(j.get("localTradedAt", ""))[:10] or None
        if price > 0:
            return price, chg, as_of
    except Exception as e:
        print(f"  ! 네이버 {code}: {e}")
    return None


def yahoo_quote(symbol):
    """Yahoo Finance 최근 두 확정 종가: (종가, 등락률%, 날짜)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=10d&interval=1d"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read().decode("utf-8"))["chart"]["result"][0]
        meta = res["meta"]
        tz = ZoneInfo(meta["exchangeTimezoneName"])
        bars = {datetime.fromtimestamp(t, tz).date(): c
                for t, c in zip(res.get("timestamp") or [], res["indicators"]["quote"][0].get("close") or []) if c}
        last_day = datetime.fromtimestamp(meta["regularMarketTime"], tz).date()
        closes = settled_closes(bars, last_day, float(meta["regularMarketPrice"]), datetime.now(tz),
                                CLOSE_MIN.get(meta["exchangeTimezoneName"]))
    except Exception as e:
        print(f"  ! Yahoo {symbol}: {e}")
        return None
    if not closes:
        return None
    day, price = closes[-1]
    prev = closes[-2][1] if len(closes) > 1 else price
    if not math.isfinite(price) or price <= 0:
        return None
    return price, (price / prev - 1) * 100 if prev else 0.0, day.isoformat()


def selftest():
    d = date(2026, 10, 7)
    bars = {date(2026, 10, 5): 100.0, date(2026, 10, 6): 110.0}  # Yahoo 가 10/7 일봉을 빠뜨린 상황
    ny = ZoneInfo("America/New_York")
    after = datetime(2026, 10, 7, 20, 43, tzinfo=ny)   # 장 마감 후 → 10/7 종가를 meta 값으로 채움
    assert settled_closes(bars, d, 99.0, after, CLOSE_MIN["America/New_York"])[-2:] == [(date(2026, 10, 6), 110.0), (d, 99.0)]
    during = datetime(2026, 10, 7, 11, 0, tzinfo=ny)   # 장중 → 10/7 값은 빼고 10/6 이 마지막
    assert settled_closes({**bars, d: 105.0}, d, 105.0, during, CLOSE_MIN["America/New_York"])[-1] == (date(2026, 10, 6), 110.0)
    nextday = datetime(2026, 10, 8, 8, 0, tzinfo=ny)   # 다음 날 프리마켓 → 10/7 종가 유지
    assert settled_closes(bars, d, 99.0, nextday, CLOSE_MIN["America/New_York"])[-1] == (d, 99.0)
    assert settled_closes(bars, d, 1400.0, during, None)[-1] == (d, 1400.0)  # 환율: 항상 최신 값
    print("selftest ok")


def quote(h):
    if h["market"] == "KR":
        return naver_quote(h["ticker"]) or yahoo_quote(h.get("yahoo") or f"{h['ticker']}.KS")
    return yahoo_quote(h.get("yahoo") or h["ticker"])


def dca_qty(h, today):
    """적립식 매수를 반영한 현재 수량과 표시용 문구."""
    dca = h.get("dca")
    if not dca:
        return h["qty"], None
    wd = WEEKDAYS.get(dca.get("weekday", "월"), 0)
    since = date.fromisoformat(dca["since"])
    shares = int(dca.get("shares", 0))
    # 오늘 새벽 6시 실행 기준: 어제까지 지난 매수일만 센다 (월요일 9시 매수 → 화요일 기록부터 반영)
    d = since + timedelta(days=(wd - since.weekday()) % 7)
    count = 0
    while d < today:
        count += 1
        d += timedelta(days=7)
    return h["qty"] + shares * count, f"매주 {dca.get('weekday', '월')} +{shares}"


def main():
    holdings = json.loads(HOLDINGS.read_text(encoding="utf-8"))["holdings"]
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"snapshots": []}
    snaps = sorted(history.get("snapshots", []), key=lambda s: s["date"])
    prev = snaps[-1] if snaps else None
    prev_by_id = {h["id"]: h for h in (prev or {}).get("holdings", [])}

    now = datetime.now(KST)
    today = now.date()

    fx_res = yahoo_quote("KRW=X")
    fx = round(fx_res[0], 2) if fx_res else (prev or {}).get("fx", {}).get("usdkrw")
    if not fx_res:
        print(f"  ! 환율을 받지 못해 이전 값 {fx} 사용")
    if not fx:
        raise SystemExit("환율이 없어 계산할 수 없습니다.")

    rows, stale = [], []
    for h in holdings:
        res = quote(h)
        old = prev_by_id.get(h["id"])
        if res and old and old.get("price") and abs(res[0] / old["price"] - 1) > 0.5:
            print(f"  ! {h['ticker']}: 전일 기록 대비 큰 변동, 확인 필요")
        if res:
            price, chg, as_of = res
        elif old:
            price, chg, as_of = old["price"], 0.0, old.get("asOf")
            stale.append(h["name"])
        else:
            print(f"  ! {h['ticker']}: 가격 없음, 제외")
            stale.append(h["name"])
            continue
        qty, dca_text = dca_qty(h, today)
        row = {
            "id": h["id"], "name": h["name"], "label": h.get("label", h["ticker"]),
            "group": h.get("group", "기타"), "account": h.get("account", "일반"),
            "ticker": h["ticker"], "market": h["market"], "currency": h["currency"],
            "qty": qty, "price": round(price, 4), "chgPct": round(chg, 2), "asOf": as_of,
        }
        if dca_text:
            row["dca"] = dca_text
        if is_delayed(as_of, today):
            row["delayed"] = True
            print(f"  ! {h['ticker']}: 시세가 {as_of} 기준으로 지연됨")
        rows.append(row)

    snap = {
        "date": today.isoformat(),
        "updatedAt": now.isoformat(timespec="seconds"),
        "fx": {"usdkrw": fx, "source": "Yahoo Finance KRW=X"},
        "holdings": rows,
    }
    snaps = [s for s in snaps if s["date"] != snap["date"]] + [snap]
    snaps = snaps[-MAX_SNAPSHOTS:]
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps({"snapshots": snaps}, ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(r["qty"] * r["price"] * (fx if r["currency"] == "USD" else 1) for r in rows)
    print(f"{snap['date']} 기록 완료: 총 {total:,.0f}원, 환율 {fx}")
    if stale:
        print("갱신 실패(이전 가격 유지):", ", ".join(stale))


if __name__ == "__main__":
    selftest() if sys.argv[1:] == ["--selftest"] else main()
