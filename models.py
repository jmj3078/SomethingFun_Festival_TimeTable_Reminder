from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ---------------------------------------------------------------------------
# Pydantic schemas — used to validate Claude Vision API responses
# ---------------------------------------------------------------------------

class PerformanceSlot(BaseModel):
    artist: str
    stage: str
    start_time: str        # "14:30" (24h format)
    end_time: Optional[str] = None
    date: Optional[str] = None  # "2026-08-15" or "Saturday" or None for single-day


class ParsedTimetable(BaseModel):
    festival_name: Optional[str] = None
    dates: list[str] = []
    timezone: Optional[str] = None  # raw TZ string from image, e.g. "KST", "UTC+9"
    performances: list[PerformanceSlot]
    parse_warnings: list[str] = []


# ---------------------------------------------------------------------------
# SQLAlchemy ORM models — persisted to SQLite
# ---------------------------------------------------------------------------

class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    raw_json = Column(Text, nullable=False)       # Full ParsedTimetable as JSON
    festival_name = Column(String, nullable=True)
    timezone_str = Column(String, nullable=True)  # Raw TZ string from Claude
    image_filename = Column(String, nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    timetable_id = Column(Integer, ForeignKey("timetables.id"), nullable=False)
    email = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    performance_dt = Column(DateTime, nullable=False)  # UTC naive datetime
    notify_minutes = Column(Integer, nullable=False)   # 10, 20, or 30
    notify_at = Column(DateTime, nullable=False)       # performance_dt - notify_minutes
    sent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
