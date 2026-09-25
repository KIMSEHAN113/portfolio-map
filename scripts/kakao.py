"""카카오톡 '나에게 보내기'로 아침 브리핑을 보낸다.

  python scripts/kakao.py          브리핑 발송 (briefing/meta.json 필요)
  python scripts/kakao.py setup    최초 1회: 인가 코드(KAKAO_AUTH_CODE)로 토큰을 받아 GitHub Secret 에 저장

환경 변수 (GitHub Secrets)
  KAKAO_REST_KEY        카카오 앱 REST API 키
  KAKAO_CLIENT_SECRET   (선택) 앱에서 Client Secret 을 켰다면
  KAKAO_REFRESH_TOKEN   setup 이 저장하는 리프레시 토큰
  GH_PAT                (선택) 토큰이 갱신될 때 Secret 을 자동으로 바꾸기 위한 GitHub 토큰
  BRIEF_URL             브리핑 페이지 주소 (예: https://kimsehan113.github.io/portfolio-map/briefing/)
  FORCE_SEND=1          일·월요일에도 보냄 (평소에는 새 시세가 없는 일·월요일은 건너뜀)

토큰 값은 절대 출력하지 않는다. 공개 저장소의 Actions 로그는 누구나 볼 수 있다.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "briefing" / "meta.json"
KST = timezone(timedelta(hours=9))


def post(url, data, token=None):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            j = json.loads(body)
            msg = j.get("error_description") or j.get("msg") or body
        except Exception:
            msg = body
        raise SystemExit(f"카카오 API 오류 {e.code}: {msg[:200]}")


def mask(value):
    if value and os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{value}")


def save_secret(name, value):
    """GH_PAT 가 있으면 GitHub Secret 을 갱신한다. 성공 여부를 돌려준다."""
    repo, pat = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_PAT")
    if not (repo and pat):
        return False
    r = subprocess.run(["gh", "secret", "set", name, "--repo", repo, "--body", value],
                       env={**os.environ, "GH_TOKEN": pat}, capture_output=True, text=True)
    if r.returncode:
        print(f"  ! Secret {name} 저장 실패: {r.stderr.strip()[:200]}")
    return r.returncode == 0


def token_request(extra):
    data = {"client_id": os.environ["KAKAO_REST_KEY"], **extra}
    if os.environ.get("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = os.environ["KAKAO_CLIENT_SECRET"]
    j = post("https://kauth.kakao.com/oauth/token", data)
    mask(j.get("access_token"))
    mask(j.get("refresh_token"))
    return j


def setup():
    code = os.environ.get("KAKAO_AUTH_CODE", "").strip()
    if "code=" in code:  # 주소창 전체를 붙여넣어도 된다
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [""])[0]
    mask(code)
    if not code:
        raise SystemExit("인가 코드가 비어 있어요.")
    j = token_request({"grant_type": "authorization_code", "code": code,
                       "redirect_uri": os.environ["BRIEF_URL"]})
    if not save_secret("KAKAO_REFRESH_TOKEN", j["refresh_token"]):
        raise SystemExit("리프레시 토큰을 Secret 에 저장하지 못했어요. GH_PAT 설정을 확인해 주세요.")
    days = int(j.get("refresh_token_expires_in", 0)) // 86400
    print(f"완료: 리프레시 토큰을 저장했어요 (유효 {days}일, 사용할 때마다 자동 갱신).")
    send_text(j["access_token"], "아침 브리핑 연결이 끝났어요. 내일 아침부터 이 채팅으로 브리핑이 와요.")


def send_text(access, message):
    tpl = {"object_type": "text", "text": message[:200],
           "link": {"web_url": os.environ["BRIEF_URL"], "mobile_web_url": os.environ["BRIEF_URL"]}}
    post("https://kapi.kakao.com/v2/api/talk/memo/default/send", {"template_object": json.dumps(tpl, ensure_ascii=False)}, access)


def send():
    now = datetime.now(KST)
    if now.weekday() in (6, 0) and os.environ.get("FORCE_SEND") != "1":
        print("일·월요일은 새 시세가 없어 건너뛰어요. (FORCE_SEND=1 이면 보냄)")
        return
    meta = json.loads(META.read_text(encoding="utf-8"))
    j = token_request({"grant_type": "refresh_token", "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"]})
    note = ""
    if j.get("refresh_token"):  # 만료 한 달 전부터 새 리프레시 토큰이 온다
        if save_secret("KAKAO_REFRESH_TOKEN", j["refresh_token"]):
            print("리프레시 토큰 갱신 완료")
        else:
            note = "\n※ 카카오 토큰 갱신이 필요해요 (GH_PAT 미설정)"

    base = os.environ["BRIEF_URL"].rstrip("/") + "/"
    v = meta["stamp"]
    view = f"{base}?v={v}"
    arrow = "▲" if meta["diff"] > 0 else "▼" if meta["diff"] < 0 else "·"
    movers = " · ".join(f"{m['name']} {m['chgPct']:+.2f}%" for m in meta["movers"][:3])
    desc = f"크게 움직인 종목: {movers}" if movers else ""
    if meta.get("headline"):
        desc += f"\n미국: {meta['headline']}"
    tpl = {
        "object_type": "feed",
        "content": {
            "title": f"{meta['date'][5:].replace('-', '/')} 아침 브리핑 · {meta['totalText']} {arrow}{meta['pct']:+.2f}%",
            "description": (desc + note)[:200],
            "image_url": f"{base}slide-1.png?v={v}", "image_width": 1600, "image_height": 900,
            "link": {"web_url": view, "mobile_web_url": view},
        },
        "buttons": [
            {"title": "슬라이드 보기", "link": {"web_url": view, "mobile_web_url": view}},
            {"title": "PPT 받기", "link": {"web_url": f"{base}briefing.pptx?v={v}", "mobile_web_url": f"{base}briefing.pptx?v={v}"}},
        ],
    }
    r = post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
             {"template_object": json.dumps(tpl, ensure_ascii=False)}, j["access_token"])
    print("카카오톡 발송 완료" if r.get("result_code") == 0 else f"발송 응답: {r}")


if __name__ == "__main__":
    setup() if sys.argv[1:] == ["setup"] else send()
