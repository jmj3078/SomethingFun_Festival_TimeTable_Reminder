from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Subscription, Timetable
from scheduler import check_and_send_notifications


@pytest.fixture()
def in_memory_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return factory


def make_timetable(session) -> Timetable:
    tt = Timetable(
        raw_json='{"festival_name": "Test Fest", "dates": [], "timezone": null, "performances": [], "parse_warnings": []}',
        festival_name="Test Fest",
        image_filename="test.jpg",
    )
    session.add(tt)
    session.commit()
    return tt


def make_subscription(session, timetable_id: int, notify_at: datetime) -> Subscription:
    performance_dt = notify_at + timedelta(minutes=20)
    sub = Subscription(
        timetable_id=timetable_id,
        email="fan@example.com",
        artist="Test Artist",
        stage="Main Stage",
        performance_dt=performance_dt,
        notify_minutes=20,
        notify_at=notify_at,
        sent=False,
    )
    session.add(sub)
    session.commit()
    return sub


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_due_subscription_is_sent(in_memory_session_factory):
    with in_memory_session_factory() as session:
        tt = make_timetable(session)
        past_notify_at = datetime.utcnow() - timedelta(minutes=1)
        make_subscription(session, tt.id, past_notify_at)

    with patch("scheduler.send_notification_email") as mock_send:
        count = check_and_send_notifications(in_memory_session_factory)

    assert count == 1
    mock_send.assert_called_once()


def test_due_subscription_marked_sent(in_memory_session_factory):
    with in_memory_session_factory() as session:
        tt = make_timetable(session)
        past_notify_at = datetime.utcnow() - timedelta(minutes=1)
        sub = make_subscription(session, tt.id, past_notify_at)
        sub_id = sub.id

    with patch("scheduler.send_notification_email"):
        check_and_send_notifications(in_memory_session_factory)

    with in_memory_session_factory() as session:
        sub = session.get(Subscription, sub_id)
        assert sub.sent is True


def test_future_subscription_not_sent(in_memory_session_factory):
    with in_memory_session_factory() as session:
        tt = make_timetable(session)
        future_notify_at = datetime.utcnow() + timedelta(hours=1)
        make_subscription(session, tt.id, future_notify_at)

    with patch("scheduler.send_notification_email") as mock_send:
        count = check_and_send_notifications(in_memory_session_factory)

    assert count == 0
    mock_send.assert_not_called()


def test_failed_send_keeps_sent_false(in_memory_session_factory):
    from email_sender import EmailSendError

    with in_memory_session_factory() as session:
        tt = make_timetable(session)
        past_notify_at = datetime.utcnow() - timedelta(minutes=1)
        sub = make_subscription(session, tt.id, past_notify_at)
        sub_id = sub.id

    with patch("scheduler.send_notification_email", side_effect=EmailSendError("smtp down")):
        count = check_and_send_notifications(in_memory_session_factory)

    assert count == 0
    with in_memory_session_factory() as session:
        sub = session.get(Subscription, sub_id)
        assert sub.sent is False


def test_failed_send_retried_on_next_tick(in_memory_session_factory):
    from email_sender import EmailSendError

    with in_memory_session_factory() as session:
        tt = make_timetable(session)
        past_notify_at = datetime.utcnow() - timedelta(minutes=1)
        make_subscription(session, tt.id, past_notify_at)

    with patch("scheduler.send_notification_email", side_effect=EmailSendError("smtp down")):
        check_and_send_notifications(in_memory_session_factory)

    with patch("scheduler.send_notification_email") as mock_send:
        count = check_and_send_notifications(in_memory_session_factory)

    assert count == 1
    mock_send.assert_called_once()


def test_multiple_subscriptions_sent(in_memory_session_factory):
    with in_memory_session_factory() as session:
        tt = make_timetable(session)
        past = datetime.utcnow() - timedelta(minutes=1)
        make_subscription(session, tt.id, past)
        make_subscription(session, tt.id, past)
        make_subscription(session, tt.id, past)

    with patch("scheduler.send_notification_email") as mock_send:
        count = check_and_send_notifications(in_memory_session_factory)

    assert count == 3
    assert mock_send.call_count == 3


def test_already_sent_subscription_not_resent(in_memory_session_factory):
    with in_memory_session_factory() as session:
        tt = make_timetable(session)
        past = datetime.utcnow() - timedelta(minutes=1)
        sub = make_subscription(session, tt.id, past)
        sub.sent = True
        session.commit()

    with patch("scheduler.send_notification_email") as mock_send:
        count = check_and_send_notifications(in_memory_session_factory)

    assert count == 0
    mock_send.assert_not_called()
