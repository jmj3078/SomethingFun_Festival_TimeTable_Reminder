import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models import Base, ParsedTimetable, PerformanceSlot

FIXTURES = Path(__file__).parent / "fixtures"


def make_parsed_timetable() -> ParsedTimetable:
    return ParsedTimetable(
        festival_name="Test Fest",
        dates=["2026-08-15"],
        timezone="KST",
        performances=[
            PerformanceSlot(artist="IU", stage="Main Stage", start_time="20:00", end_time="21:30", date="2026-08-15"),
            PerformanceSlot(artist="NewJeans", stage="Green Stage", start_time="17:00", date="2026-08-15"),
        ],
        parse_warnings=[],
    )


@pytest.fixture()
def client():
    # StaticPool ensures create_all and session share the same in-memory connection
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "업로드" in resp.text


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------

def test_upload_success_redirects_to_timetable(client):
    fake_timetable = make_parsed_timetable()
    image_bytes = (FIXTURES / "sample_response.json").read_bytes()  # any bytes work

    with patch("main.parse_timetable_image", return_value=fake_timetable):
        resp = client.post(
            "/upload",
            files=[("images", ("test.jpg", image_bytes, "image/jpeg"))],
            follow_redirects=False,
        )

    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/timetable/")


def test_upload_multiple_images_passes_all_to_vision(client):
    fake_timetable = make_parsed_timetable()
    captured = {}

    def capture_call(images):
        captured["images"] = images
        return fake_timetable

    with patch("main.parse_timetable_image", side_effect=capture_call):
        client.post(
            "/upload",
            files=[
                ("images", ("day1.jpg", b"bytes1", "image/jpeg")),
                ("images", ("day2.jpg", b"bytes2", "image/png")),
            ],
            follow_redirects=False,
        )

    assert len(captured["images"]) == 2
    assert captured["images"][0][1] == "image/jpeg"
    assert captured["images"][1][1] == "image/png"


def test_upload_parse_error_shows_error_page(client):
    from vision import VisionParseError
    image_bytes = b"bad image"

    with patch("main.parse_timetable_image", side_effect=VisionParseError("failed", raw_response="raw")):
        resp = client.post(
            "/upload",
            files=[("images", ("test.jpg", image_bytes, "image/jpeg"))],
        )

    assert resp.status_code == 422
    assert "타임테이블을 읽을 수 없었습니다" in resp.text


# ---------------------------------------------------------------------------
# GET /timetable/{id}
# ---------------------------------------------------------------------------

def test_timetable_page_shows_artists(client):
    fake_timetable = make_parsed_timetable()

    with patch("main.parse_timetable_image", return_value=fake_timetable):
        upload_resp = client.post(
            "/upload",
            files=[("images", ("test.jpg", b"bytes", "image/jpeg"))],
            follow_redirects=True,
        )

    assert "IU" in upload_resp.text
    assert "NewJeans" in upload_resp.text


def test_timetable_not_found_redirects(client):
    resp = client.get("/timetable/9999", follow_redirects=False)
    assert resp.status_code == 303


# ---------------------------------------------------------------------------
# POST /subscribe
# ---------------------------------------------------------------------------

def test_subscribe_creates_subscriptions(client):
    fake_timetable = make_parsed_timetable()

    with patch("main.parse_timetable_image", return_value=fake_timetable):
        client.post("/upload", files=[("images", ("test.jpg", b"bytes", "image/jpeg"))])

    resp = client.post(
        "/subscribe",
        data={
            "timetable_id": "1",
            "email": "fan@example.com",
            "notify_minutes": "20",
            "festival_date": "2026-08-15",
            "user_timezone": "Asia/Seoul",
            "artists": ["IU||Main Stage||20:00"],
        },
    )
    assert resp.status_code == 200
    assert "IU" in resp.text
    assert "fan@example.com" in resp.text


def test_subscribe_no_artists_shows_error(client):
    fake_timetable = make_parsed_timetable()

    with patch("main.parse_timetable_image", return_value=fake_timetable):
        client.post("/upload", files=[("images", ("test.jpg", b"bytes", "image/jpeg"))])

    resp = client.post(
        "/subscribe",
        data={
            "timetable_id": "1",
            "email": "fan@example.com",
            "notify_minutes": "20",
            "festival_date": "2026-08-15",
            "user_timezone": "Asia/Seoul",
        },
    )
    assert resp.status_code == 200
    assert "아티스트" in resp.text


# ---------------------------------------------------------------------------
# GET /api/timetable/{id}
# ---------------------------------------------------------------------------

def test_api_timetable_returns_json(client):
    fake_timetable = make_parsed_timetable()

    with patch("main.parse_timetable_image", return_value=fake_timetable):
        client.post("/upload", files=[("images", ("test.jpg", b"bytes", "image/jpeg"))])

    resp = client.get("/api/timetable/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["festival_name"] == "Test Fest"
    assert len(data["performances"]) == 2


def test_api_timetable_not_found(client):
    resp = client.get("/api/timetable/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /admin/subscriptions
# ---------------------------------------------------------------------------

def test_admin_subscriptions_returns_list(client):
    resp = client.get("/admin/subscriptions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
