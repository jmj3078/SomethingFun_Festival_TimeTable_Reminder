import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from typing import List
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import config
from database import SessionLocal, get_db, init_db
from models import ParsedTimetable, Subscription, Timetable
from scheduler import create_scheduler
from vision import VisionParseError, parse_timetable_image

os.makedirs(config.UPLOAD_DIR, exist_ok=True)
templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = create_scheduler(SessionLocal)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Festival Timetable Reminder", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "index.html", {"error": error})


@app.post("/upload")
async def upload_image(request: Request, images: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    if not images:
        return templates.TemplateResponse(request, "index.html", {"error": "이미지를 선택해주세요."}, status_code=400)

    # Read and validate all images
    image_data: list[tuple[bytes, str]] = []
    for img in images:
        data = await img.read()
        if len(data) > config.MAX_IMAGE_SIZE_MB * 1024 * 1024:
            return templates.TemplateResponse(
                request, "index.html",
                {"error": f"'{img.filename}' 파일이 너무 큽니다. 최대 {config.MAX_IMAGE_SIZE_MB}MB."},
                status_code=400,
            )
        mime_type = img.content_type or "image/jpeg"
        if mime_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            mime_type = "image/jpeg"
        image_data.append((data, mime_type))

    # Parse all images together with Claude Vision
    try:
        timetable_data = parse_timetable_image(image_data)
    except VisionParseError as e:
        return templates.TemplateResponse(
            request, "index.html",
            {
                "error": "타임테이블을 읽을 수 없었습니다. 더 선명한 이미지를 사용해주세요.",
                "raw_response": e.raw_response[:500] if e.raw_response else "",
            },
            status_code=422,
        )

    # Save all images to disk; store filenames as JSON array
    filenames = []
    for img, (data, _) in zip(images, image_data):
        ext = os.path.splitext(img.filename or "image.jpg")[1] or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        with open(os.path.join(config.UPLOAD_DIR, filename), "wb") as f:
            f.write(data)
        filenames.append(filename)

    tt = Timetable(
        raw_json=timetable_data.model_dump_json(),
        festival_name=timetable_data.festival_name,
        timezone_str=timetable_data.timezone,
        image_filename=json.dumps(filenames),
    )
    db.add(tt)
    db.commit()
    db.refresh(tt)

    return RedirectResponse(url=f"/timetable/{tt.id}", status_code=303)


@app.get("/timetable/{timetable_id}", response_class=HTMLResponse)
async def show_timetable(request: Request, timetable_id: int, db: Session = Depends(get_db)):
    tt = db.get(Timetable, timetable_id)
    if not tt:
        return RedirectResponse(url="/?error=타임테이블을 찾을 수 없습니다", status_code=303)

    timetable_data = ParsedTimetable.model_validate_json(tt.raw_json)

    # Group performances by stage for display
    stages: dict[str, list] = {}
    for perf in timetable_data.performances:
        stages.setdefault(perf.stage, []).append(perf)

    return templates.TemplateResponse(
        request, "timetable.html",
        {
            "timetable": tt,
            "timetable_data": timetable_data,
            "stages": stages,
        },
    )


@app.post("/subscribe")
async def create_subscriptions(
    request: Request,
    timetable_id: int = Form(...),
    email: str = Form(...),
    notify_minutes: int = Form(...),
    festival_date: str = Form(...),
    user_timezone: str = Form(...),
    db: Session = Depends(get_db),
):
    tt = db.get(Timetable, timetable_id)
    if not tt:
        return RedirectResponse(url="/", status_code=303)

    form_data = await request.form()
    selected_artists = form_data.getlist("artists")

    if not selected_artists:
        timetable_data = ParsedTimetable.model_validate_json(tt.raw_json)
        stages: dict[str, list] = {}
        for perf in timetable_data.performances:
            stages.setdefault(perf.stage, []).append(perf)
        return templates.TemplateResponse(
            request, "timetable.html",
            {
                "timetable": tt,
                "timetable_data": timetable_data,
                "stages": stages,
                "error": "알림을 받을 아티스트를 하나 이상 선택해주세요.",
            },
        )

    timetable_data = ParsedTimetable.model_validate_json(tt.raw_json)
    created_subs = []

    for perf in timetable_data.performances:
        artist_key = f"{perf.artist}||{perf.stage}||{perf.start_time}"
        if artist_key not in selected_artists:
            continue

        try:
            performance_dt = resolve_performance_utc(perf.start_time, festival_date, user_timezone)
        except (ValueError, ZoneInfoNotFoundError):
            continue

        notify_at = performance_dt - timedelta(minutes=notify_minutes)

        sub = Subscription(
            timetable_id=timetable_id,
            email=email,
            artist=perf.artist,
            stage=perf.stage,
            performance_dt=performance_dt,
            notify_minutes=notify_minutes,
            notify_at=notify_at,
            sent=False,
        )
        db.add(sub)
        created_subs.append(sub)

    db.commit()
    for sub in created_subs:
        db.refresh(sub)

    return templates.TemplateResponse(
        request, "confirm.html",
        {"subscriptions": created_subs, "email": email, "user_timezone": user_timezone},
    )


@app.get("/api/timetable/{timetable_id}")
async def api_get_timetable(timetable_id: int, db: Session = Depends(get_db)):
    tt = db.get(Timetable, timetable_id)
    if not tt:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(json.loads(tt.raw_json))


@app.get("/admin/subscriptions")
async def admin_subscriptions(db: Session = Depends(get_db)):
    subs = db.query(Subscription).all()
    return JSONResponse([
        {
            "id": s.id,
            "email": s.email,
            "artist": s.artist,
            "stage": s.stage,
            "notify_at": s.notify_at.isoformat(),
            "notify_minutes": s.notify_minutes,
            "sent": s.sent,
        }
        for s in subs
    ])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def resolve_performance_utc(time_str: str, date_str: str, tz_name: str) -> datetime:
    """Convert 'HH:MM', 'YYYY-MM-DD', 'Asia/Seoul' -> UTC naive datetime."""
    local_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    local_dt = local_dt.replace(tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
