"""매일 보유 종목의 종가와 USD/KRW 환율을 받아 data/history.json 에 하루치 기록을 추가한다.

GitHub Actions 에서 매일 오전 6시(한국시간)에 실행된다.
수량을 바꾸려면 holdings.json 의 qty 만 고치면 된다.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
HOLDINGS = ROOT / "holdings.json"
HISTORY = ROOT / "data" / "history.json"
KST = timezone(timedelta(hours=9))
MAX_SNAPSHOTS = 900


def last_two_closes(symbol):
    """최근 두 거래일 종가와 마지막 종가 날짜. 실패하면 None."""
    try:
        df = yf.Ticker(symbol).history(period="15d", interval="1d", auto_adjust=False)
    except Exception as e:  # 네트워크 오류 등
        print(f"  ! {symbol}: {e}")
        return None
    if df is None or df.empty or "Close" not in df:
        print(f"  ! {symbol}: 데이터 없음")
        return None
    closes = df["Close"].dropna()
    if closes.empty:
        return None
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) > 1 else price
    if not math.isfinite(price) or price <= 0:
        return None
    as_of = closes.index[-1].strftime("%Y-%m-%d")
    chg = (price / prev - 1) * 100 if prev else 0.0
    return price, chg, as_of


def main():
    holdings = json.loads(HOLDINGS.read_text(encoding="utf-8"))["holdings"]
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"snapshots": []}
    snaps = sorted(history.get("snapshots", []), key=lambda s: s["date"])
    prev = snaps[-1] if snaps else None
    prev_by_id = {h["id"]: h for h in (prev or {}).get("holdings", [])}

    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")

    fx_res = last_two_closes("KRW=X")
    if fx_res:
        fx = round(fx_res[0], 2)
    else:
        fx = (prev or {}).get("fx", {}).get("usdkrw")
        print(f"  ! 환율을 받지 못해 이전 값 {fx} 사용")
    if not fx:
        raise SystemExit("환율이 없어 계산할 수 없습니다.")

    rows, stale = [], []
    for h in holdings:
        res = last_two_closes(h.get("yahoo") or h["ticker"])
        old = prev_by_id.get(h["id"])
        if res and old and old.get("price"):
            jump = abs(res[0] / old["price"] - 1)
            if jump > 0.5:  # 액면분할 등 이상치 의심
                print(f"  ! {h['ticker']}: 전일 대비 {jump:.0%} 변동, 확인 필요")
        if res:
            price, chg, as_of = res
        elif old:
            price, chg, as_of = old["price"], 0.0, old.get("asOf")
            stale.append(h["name"])
        else:
            print(f"  ! {h['ticker']}: 가격 없음, 제외")
            stale.append(h["name"])
            continue
        rows.append({
            "id": h["id"], "name": h["name"], "label": h.get("label", h["ticker"]),
            "group": h.get("group", "기타"), "ticker": h["ticker"], "market": h["market"],
            "currency": h["currency"], "qty": h["qty"],
            "price": round(price, 4), "chgPct": round(chg, 2), "asOf": as_of,
        })

    snap = {
        "date": today,
        "updatedAt": now.isoformat(timespec="seconds"),
        "fx": {"usdkrw": fx, "source": "Yahoo Finance KRW=X"},
        "holdings": rows,
    }
    snaps = [s for s in snaps if s["date"] != today] + [snap]
    snaps = snaps[-MAX_SNAPSHOTS:]
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps({"snapshots": snaps}, ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(r["qty"] * r["price"] * (fx if r["currency"] == "USD" else 1) for r in rows)
    print(f"{today} 기록 완료: 총 {total:,.0f}원, 환율 {fx}")
    if stale:
        print("갱신 실패(이전 가격 유지):", ", ".join(stale))


if __name__ == "__main__":
    main()
