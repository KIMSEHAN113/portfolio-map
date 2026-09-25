# 데일리 비중 지도 · GitHub Pages 설정 가이드

완성되면 `https://<내 GitHub 아이디>.github.io/portfolio-map/` 주소로 누구나 볼 수 있고, 매일 오전 6시(한국시간)에 시세가 자동 갱신됩니다. 비용은 없습니다.

> 이 저장소는 공개(Public)입니다. 사이트뿐 아니라 `holdings.json`(보유 수량)도 누구나 볼 수 있어요.

## 폴더 구성

| 파일 | 역할 |
|---|---|
| `index.html` | 트리맵 웹페이지 |
| `holdings.json` | 보유 종목과 수량. 매수·매도 후 여기 `qty`만 고치면 됨 |
| `data/history.json` | 날짜별 시세 기록 (자동으로 쌓임) |
| `scripts/update.py` | Yahoo Finance에서 종가·환율을 받아 기록 추가 |
| `.github/workflows/update.yml` | 매일 06:00 자동 실행 + 사이트 배포 |

## 1. GitHub 가입 (약 3분)

1. https://github.com/signup 에서 이메일, 비밀번호, 아이디를 입력해 가입합니다.
2. 아이디는 사이트 주소에 들어가니 짧고 영문 소문자로 정하는 걸 추천해요.
3. 이메일로 온 인증 코드를 입력하면 끝.

## 2. 저장소 만들기

1. 오른쪽 위 `+` → **New repository**
2. Repository name: `portfolio-map`
3. **Public** 선택 (무료 계정의 GitHub Pages는 공개 저장소만 가능)
4. 나머지는 그대로 두고 **Create repository**

## 3. 파일 올리기

1. 새 저장소 화면에서 **uploading an existing file** 링크를 누릅니다.
2. 압축을 푼 폴더에서 `index.html`, `holdings.json`, `README.md`, `data` 폴더, `scripts` 폴더를 한꺼번에 끌어다 놓습니다.
3. 아래 **Commit changes** 를 누릅니다.

## 4. 자동 갱신 파일 만들기

`.github` 폴더는 이름이 점으로 시작해서 끌어다 놓기로는 빠질 수 있어서 직접 만듭니다.

1. 저장소 화면에서 **Add file → Create new file**
2. 파일 이름 칸에 `.github/workflows/update.yml` 을 그대로 입력 (슬래시를 치면 폴더가 자동으로 생겨요)
3. 압축 폴더의 `.github/workflows/update.yml` 내용을 메모장으로 열어 전체 복사 → 붙여넣기
   (맥 Finder에서 안 보이면 `Cmd + Shift + .` 을 누르면 숨김 폴더가 보여요)
4. **Commit changes**

## 5. GitHub Pages 켜기

1. 저장소 상단 **Settings → Pages**
2. **Build and deployment → Source** 를 **GitHub Actions** 로 선택

## 6. 첫 실행

1. 저장소 상단 **Actions** 탭 → 왼쪽 **Update portfolio map**
2. 오른쪽 **Run workflow → Run workflow**
3. 1~2분 뒤 초록 체크가 뜨면 `https://<아이디>.github.io/portfolio-map/` 접속

이후에는 매일 오전 6시쯤 자동으로 돌아요. GitHub 예약 실행은 서버 사정에 따라 10~30분 늦어질 수 있습니다.

## 수량 바꾸기

저장소에서 `holdings.json` → 연필 아이콘(Edit) → 해당 종목의 `"qty"` 숫자 수정 → **Commit changes**. 커밋하면 바로 다시 계산해서 배포됩니다.

새 종목을 추가할 때는 기존 항목을 복사해 `id`(영문 고유값), `name`, `label`(맵에 표시할 짧은 이름), `group`, `ticker`, `market`(KR/US), `currency`(KRW/USD), `qty`, `yahoo`(Yahoo Finance 심볼. 국내는 `종목코드.KS`, 코스닥은 `.KQ`)를 채우면 됩니다.

## 아침 브리핑 (PPT + 카카오톡)

매일 시세 갱신 뒤 `scripts/briefing.py` 가 3장짜리 PPT(보유 주식 변동 → 변동 사유 → 미국 뉴스)를 만들고,
`https://kimsehan113.github.io/portfolio-map/briefing/` 에 슬라이드 이미지·PPT·PDF로 올립니다.
카카오톡을 연결하면 화~토 아침마다 "나와의 채팅"으로 요약 카드와 링크가 와요. (일·월요일은 새 시세가 없어 건너뜀)

- 변동 사유는 AI 분석이 아니라 Google 뉴스 헤드라인 모음이에요. 실제 원인과 다를 수 있어요.
- 미국 뉴스는 연합뉴스 시장 RSS와 한국경제 국제 RSS의 제목·요약문이에요.
- 저장소가 공개라서 브리핑 페이지도 주소를 아는 누구나 볼 수 있어요 (검색 엔진 노출은 막아 둠).

### 카카오톡 연결 (최초 1회, 약 15분)

**카카오 쪽** — https://developers.kakao.com 에 카카오 계정으로 로그인

1. **내 애플리케이션 → 애플리케이션 추가하기** (이름 예: 아침 브리핑)
2. **앱 키**에서 **REST API 키**를 복사해 둡니다.
3. **플랫폼 → Web → 사이트 도메인**에 `https://kimsehan113.github.io` 등록
4. **카카오 로그인**을 **활성화(ON)**, **Redirect URI**에 `https://kimsehan113.github.io/portfolio-map/briefing/` 등록
5. **동의항목 → 카카오톡 메시지 전송(talk_message)** 을 **선택 동의**로 설정
6. (보안 → Client Secret 을 켰다면 코드를 복사해 둡니다. 안 켰으면 넘어가도 돼요.)

**GitHub 쪽**

7. GitHub 오른쪽 위 프로필 → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
   - Repository access: **Only select repositories → portfolio-map**
   - Permissions → Repository permissions → **Secrets: Read and write**
   - 만든 토큰을 복사 (카카오 토큰을 자동 갱신할 때 씀)
8. 이 저장소 **Settings → Secrets and variables → Actions → New repository secret** 으로 추가
   - `KAKAO_REST_KEY` = 2번의 REST API 키
   - `GH_PAT` = 7번의 토큰
   - `KAKAO_CLIENT_SECRET` = 6번 코드 (켠 경우만)

**연결하기** (9~10번은 10분 안에 이어서)

9. 브라우저 주소창에 아래 주소를 넣고 `<REST API 키>` 부분만 바꿔서 접속 → 동의하고 계속하기
   ```
   https://kauth.kakao.com/oauth/authorize?client_id=<REST API 키>&redirect_uri=https://kimsehan113.github.io/portfolio-map/briefing/&response_type=code&scope=talk_message
   ```
10. 이동한 페이지의 **주소창 주소 전체**를 복사 → **Actions → Kakao setup (최초 1회) → Run workflow** 에 붙여넣고 실행
11. 카카오톡 "나와의 채팅"에 *연결이 끝났어요* 메시지가 오면 성공
12. 바로 받아보려면 **Actions → Update portfolio map → Run workflow** 에서 *카카오톡 브리핑도 보내기*를 체크하고 실행

카카오 토큰은 쓸 때마다 자동으로 연장돼요. 두 달 넘게 한 번도 발송되지 않으면 9~10번을 다시 하면 됩니다.

## 문제가 생기면

- **Actions 실행이 빨간 X**: 해당 실행을 눌러 로그를 보면 어느 종목에서 실패했는지 나와요. 한 종목이 실패해도 이전 가격으로 채우고 계속 진행합니다.
- **사이트가 404**: 5단계의 Source가 GitHub Actions인지 확인하고, 6단계를 한 번 더 실행하세요.
