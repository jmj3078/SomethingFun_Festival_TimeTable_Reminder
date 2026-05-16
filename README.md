# 🎵 Festival Timetable Reminder

페스티벌 타임테이블 이미지를 업로드하면, 공연 시작 전에 이메일로 알림을 보내주는 웹 서비스입니다.

인스타그램·공식 사이트에 올라온 타임테이블 이미지를 그대로 올리면 Claude AI가 자동으로 공연 정보를 추출합니다.

---

## 기능

- 타임테이블 이미지 **여러 장** 동시 업로드 (Day 1 / Day 2, 스테이지별 분리 이미지 모두 지원)
- Claude Vision AI가 이미지에서 아티스트·스테이지·시간 자동 추출
- 보고 싶은 아티스트만 선택해서 알림 신청
- **10분 / 20분 / 30분 전** 중 원하는 시간에 이메일 알림
- 발송 실패 시 다음 체크 시점에 자동 재시도

---

## 시작하기

### 필요한 것

| 항목 | 설명 |
|------|------|
| Python 3.10+ | [python.org](https://www.python.org/downloads/) |
| Google Gemini API 키 | [aistudio.google.com](https://aistudio.google.com/apikey) — 무료 발급 가능 |
| Gmail 계정 | 이메일 발송용 (다른 SMTP도 가능) |

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/your-username/TimeTable_Reminder.git
cd TimeTable_Reminder

# 2. 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt
```

### 환경 변수 설정

`.env` 파일을 프로젝트 루트에 만들고 아래 내용을 채워넣으세요.

```env
# Google Gemini AI (필수) — https://aistudio.google.com/apikey 에서 무료 발급
GEMINI_API_KEY=AIza...
# GEMINI_MODEL=gemini-2.5-flash   # 기본값, 필요시 변경

# 이메일 발송 설정 (Gmail 기준)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=your@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_FROM=your@gmail.com
```

> **Gmail 앱 비밀번호 발급 방법**
> 구글 계정 → 보안 → 2단계 인증 활성화 → "앱 비밀번호" 생성 → 위 `SMTP_PASSWORD`에 입력
> (일반 Gmail 비밀번호가 아닌 앱 전용 비밀번호를 사용해야 합니다)

### 실행

```bash
uvicorn main:app --reload
```

브라우저에서 `http://localhost:8000` 접속

---

## 사용 방법

### 1. 타임테이블 이미지 업로드

홈 화면에서 타임테이블 이미지를 선택합니다. **여러 장을 한번에 선택**할 수 있습니다.

```
예시:
- Day 1 이미지 + Day 2 이미지 동시 업로드
- Main Stage 이미지 + Green Stage 이미지 동시 업로드
```

### 2. 아티스트 선택 & 알림 신청

Claude가 추출한 타임테이블을 확인하고:
- 알림 받을 아티스트를 체크
- 이메일 주소 입력
- 공연 날짜와 타임존 확인 (브라우저가 자동 감지)
- 몇 분 전 알림을 받을지 선택 (10 / 20 / 30분)

### 3. 공연 당일 자동 알림

서버가 실행 중인 동안 매 분마다 알림 시간을 체크하여 이메일을 발송합니다.

> ⚠️ **주의:** 공연 당일에는 서버가 실행 중이어야 합니다.

---

## 다른 이메일 서비스 사용하기

Gmail 외에 다른 SMTP 서비스도 사용할 수 있습니다.

**네이버 메일**
```env
SMTP_HOST=smtp.naver.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=your_id@naver.com
SMTP_PASSWORD=your_password
```

**Outlook / Hotmail**
```env
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=your@outlook.com
SMTP_PASSWORD=your_password
```

---

## 개발자를 위한 정보

### 프로젝트 구조

```
TimeTable_Reminder/
├── main.py          # FastAPI 라우트 (웹 서버 진입점)
├── vision.py        # Claude Vision API 이미지 파싱
├── scheduler.py     # 60초마다 알림 발송 체크
├── email_sender.py  # 이메일 렌더링 및 발송
├── models.py        # 데이터 모델 (Pydantic + SQLAlchemy)
├── database.py      # SQLite DB 연결
├── config.py        # 환경 변수
├── templates/       # HTML 템플릿
├── static/          # CSS
└── tests/           # 테스트 (50개)
```

### 테스트 실행

API 키 없이도 대부분의 테스트를 실행할 수 있습니다.

```bash
# 단위 테스트 + API 테스트 (API 키 불필요)
pytest tests/ -m "not integration" -v

# Claude API를 실제로 호출하는 통합 테스트
# tests/fixtures/sample_timetable.jpg 파일 필요
ANTHROPIC_API_KEY=sk-ant-... pytest tests/ -m integration -v
```

### 기술 스택

| 역할 | 기술 |
|------|------|
| 웹 프레임워크 | FastAPI |
| 이미지 파싱 | Google Gemini Vision API (gemini-2.5-flash) |
| DB | SQLite (SQLAlchemy) |
| 스케줄러 | APScheduler |
| 이메일 | SMTP (smtplib) |
| 템플릿 | Jinja2 |

---

## 자주 묻는 질문

**Q. 이미지 파싱이 실패하면 어떻게 되나요?**
실패 시 오류 메시지와 함께 홈 화면으로 돌아갑니다. 더 선명하거나 텍스트가 잘 보이는 이미지로 다시 시도해보세요.

**Q. 서버를 껐다 켜도 알림 신청이 유지되나요?**
네. 구독 정보는 SQLite DB (`timetable.db`)에 저장되므로 서버를 재시작해도 유지됩니다.

**Q. 알림을 취소하고 싶으면 어떻게 하나요?**
현재 UI에서 취소 기능은 없습니다. 개발 중 취소가 필요하다면 `/admin/subscriptions` 엔드포인트에서 구독 목록을 확인할 수 있습니다.

**Q. 이미지를 몇 장까지 올릴 수 있나요?**
장 수 제한은 없지만 Claude API는 이미지당 최대 5MB, 한 요청에 최대 20장을 지원합니다. 각 파일 크기 제한은 환경 변수 `MAX_IMAGE_SIZE_MB`로 조정할 수 있습니다 (기본값: 10MB).

---

## 라이선스

MIT
