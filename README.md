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

## 문제가 생기면

- **Actions 실행이 빨간 X**: 해당 실행을 눌러 로그를 보면 어느 종목에서 실패했는지 나와요. 한 종목이 실패해도 이전 가격으로 채우고 계속 진행합니다.
- **사이트가 404**: 5단계의 Source가 GitHub Actions인지 확인하고, 6단계를 한 번 더 실행하세요.
