"""
테스트용 타임테이블 이미지 생성 스크립트.

사용법:
    python make_test_image.py               # 지금 + 15분 공연, 10분 전 알림 → 5분 후 이메일
    python make_test_image.py --minutes 30  # 지금 + 30분 공연, 20분 전 알림 → 10분 후 이메일
"""
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

TIMEZONE    = ZoneInfo("Asia/Seoul")
OUTPUT_PATH = "tests/fixtures/sample_timetable.jpg"

BG     = (15, 15, 20)
HEADER = (30, 30, 40)
ACCENT = (255, 200, 50)
WHITE  = (255, 255, 255)
GRAY   = (160, 160, 180)
STAGE1 = (60, 120, 200)
STAGE2 = (180, 60, 120)
GOLD   = (40, 80, 140)
HILITE = (160, 120, 20)


def _font(size: int):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_image(minutes_from_now: int) -> dict:
    now = datetime.now(tz=TIMEZONE)

    p1s = now + timedelta(minutes=minutes_from_now)
    p1e = p1s + timedelta(minutes=60)
    p0s = p1s - timedelta(minutes=90)
    p0e = p1s - timedelta(minutes=30)
    p2s = p1e
    p2e = p1e + timedelta(minutes=75)

    gs1s = p0s + timedelta(minutes=20)
    gs1e = gs1s + timedelta(minutes=50)
    gs2s = gs1e + timedelta(minutes=15)
    gs2e = gs2s + timedelta(minutes=70)

    date_str = now.strftime("%Y-%m-%d")
    t = lambda dt: dt.strftime("%H:%M")

    W, H = 900, 620
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    f_lg = _font(36)
    f_md = _font(24)
    f_sm = _font(18)

    # Header
    d.rectangle([0, 0, W, 80], fill=HEADER)
    d.text((40, 18), "Test Festival 2026", font=f_lg, fill=ACCENT)
    d.text((40, 58), date_str + "  (KST)", font=f_sm, fill=GRAY)

    # Stage headers
    c1, c2 = 60, 480
    d.rectangle([c1 - 10, 100, c1 + 360, 135], fill=STAGE1)
    d.text((c1, 108), "MAIN STAGE", font=f_md, fill=WHITE)
    d.rectangle([c2 - 10, 100, c2 + 360, 135], fill=STAGE2)
    d.text((c2, 108), "GREEN STAGE", font=f_md, fill=WHITE)

    def slot(x, y, s, e, artist, highlight=False):
        bg  = HILITE if highlight else GOLD
        bdr = ACCENT  if highlight else (80, 80, 100)
        d.rectangle([x - 10, y, x + 360, y + 90], fill=bg, outline=bdr, width=2)
        d.text((x, y + 8),  f"{t(s)} - {t(e)}", font=f_sm, fill=GRAY)
        d.text((x, y + 34), artist, font=f_md, fill=WHITE)
        if highlight:
            d.text((x, y + 64), "** COMING UP NEXT **", font=f_sm, fill=ACCENT)

    slot(c1, 155, p0s, p0e, "DJ Openset")
    slot(c1, 265, p1s, p1e, "Test Artist A", highlight=True)
    slot(c1, 375, p2s, p2e, "Headliner B")

    slot(c2, 155, gs1s, gs1e, "Band X")
    slot(c2, 280, gs2s, gs2e, "Solo Artist Y")

    # Footer
    d.rectangle([0, H - 40, W, H], fill=HEADER)
    d.text((40, H - 26), f"Generated at {now.strftime('%H:%M:%S')} KST", font=f_sm, fill=GRAY)

    img.save(OUTPUT_PATH, "JPEG", quality=95)
    return {"perf_start": t(p1s), "date": date_str}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=15,
                        help="지금으로부터 몇 분 후 공연 (기본값: 15)")
    args = parser.parse_args()

    m = args.minutes
    # 알림 시간: 10/20/30 중 공연 시작 전에 도착할 수 있는 최대값
    if m > 20:
        notify = 20
    elif m > 10:
        notify = 10
    else:
        notify = 0  # 즉시 알림 (notify_at이 과거가 되어 서버 시작 즉시 발송)

    info = make_image(m)

    print(f"\n  이미지 생성 완료: {OUTPUT_PATH}")
    print(f"  'Test Artist A' 공연: {info['perf_start']} KST  (지금으로부터 {m}분 후)")
    print()
    print("  다음 단계:")
    print("  1. uvicorn main:app --reload  ← 서버 실행")
    print("  2. http://localhost:8000 접속")
    print(f"  3. {OUTPUT_PATH} 업로드")
    print(f"  4. 'Test Artist A' 체크, 날짜: {info['date']}, 타임존: Asia/Seoul")
    if notify > 0:
        print(f"     알림 설정: {notify}분 전  →  약 {m - notify}분 후 이메일 도착")
    else:
        print(f"     알림 설정: 10분 전  →  서버가 즉시 발송 (공연이 {m}분 후라 이미 발송 타이밍)")
    print()
