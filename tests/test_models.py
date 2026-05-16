from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import resolve_performance_utc
from models import Base, ParsedTimetable, PerformanceSlot, Subscription, Timetable


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# resolve_performance_utc — pure function tests
# ---------------------------------------------------------------------------

def test_kst_to_utc():
    # 20:00 KST = 11:00 UTC
    result = resolve_performance_utc("20:00", "2026-08-15", "Asia/Seoul")
    assert result.hour == 11
    assert result.minute == 0
    assert result.tzinfo is None  # stored as naive UTC


def test_pst_to_utc():
    # 14:30 PST (UTC-8) = 22:30 UTC
    result = resolve_performance_utc("14:30", "2026-01-15", "America/Los_Angeles")
    assert result.hour == 22
    assert result.minute == 30


def test_utc_to_utc():
    result = resolve_performance_utc("09:00", "2026-08-15", "UTC")
    assert result.hour == 9
    assert result.minute == 0


def test_invalid_timezone_raises():
    from zoneinfo import ZoneInfoNotFoundError
    with pytest.raises(ZoneInfoNotFoundError):
        resolve_performance_utc("14:30", "2026-08-15", "Not/ATimezone")


def test_invalid_time_format_raises():
    with pytest.raises(ValueError):
        resolve_performance_utc("2pm", "2026-08-15", "Asia/Seoul")


def test_invalid_date_format_raises():
    with pytest.raises(ValueError):
        resolve_performance_utc("14:30", "August 15", "Asia/Seoul")


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------

def test_parsed_timetable_defaults():
    t = ParsedTimetable(performances=[])
    assert t.festival_name is None
    assert t.dates == []
    assert t.parse_warnings == []


def test_performance_slot_optional_fields():
    slot = PerformanceSlot(artist="IU", stage="Main Stage", start_time="20:00")
    assert slot.end_time is None
    assert slot.date is None


# ---------------------------------------------------------------------------
# SQLAlchemy CRUD
# ---------------------------------------------------------------------------

def test_insert_timetable(db):
    tt = Timetable(
        raw_json='{"festival_name": "Test", "dates": [], "timezone": null, "performances": [], "parse_warnings": []}',
        festival_name="Test Fest",
        image_filename="test.jpg",
    )
    db.add(tt)
    db.commit()
    assert tt.id is not None
    assert tt.created_at is not None


def test_insert_subscription(db):
    tt = Timetable(raw_json="{}", festival_name="Fest", image_filename="img.jpg")
    db.add(tt)
    db.commit()

    sub = Subscription(
        timetable_id=tt.id,
        email="fan@example.com",
        artist="IU",
        stage="Main Stage",
        performance_dt=datetime(2026, 8, 15, 11, 0),
        notify_minutes=20,
        notify_at=datetime(2026, 8, 15, 10, 40),
    )
    db.add(sub)
    db.commit()

    assert sub.id is not None
    assert sub.sent is False


def test_query_unsent_subscriptions(db):
    tt = Timetable(raw_json="{}", festival_name="Fest", image_filename="img.jpg")
    db.add(tt)
    db.commit()

    for i in range(3):
        db.add(Subscription(
            timetable_id=tt.id,
            email=f"fan{i}@example.com",
            artist="IU",
            stage="Main Stage",
            performance_dt=datetime(2026, 8, 15, 11, 0),
            notify_minutes=20,
            notify_at=datetime(2026, 8, 15, 10, 40),
            sent=(i == 2),
        ))
    db.commit()

    unsent = db.query(Subscription).filter(Subscription.sent.is_(False)).all()
    assert len(unsent) == 2
