from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from email_sender import (
    EmailSendError,
    render_email_html,
    render_email_subject,
    render_email_text,
    send_notification_email,
)
from models import Subscription


def make_subscription(**kwargs) -> Subscription:
    defaults = dict(
        id=1,
        timetable_id=1,
        email="fan@example.com",
        artist="Billie Eilish",
        stage="Main Stage",
        performance_dt=datetime(2026, 8, 15, 11, 0),  # 20:00 KST = 11:00 UTC
        notify_minutes=20,
        notify_at=datetime(2026, 8, 15, 10, 40),
        sent=False,
    )
    defaults.update(kwargs)
    sub = Subscription()
    for k, v in defaults.items():
        setattr(sub, k, v)
    return sub


# ---------------------------------------------------------------------------
# Subject tests
# ---------------------------------------------------------------------------

def test_subject_contains_artist():
    sub = make_subscription(artist="NewJeans", notify_minutes=10)
    assert "NewJeans" in render_email_subject(sub)


def test_subject_contains_minutes():
    sub = make_subscription(notify_minutes=30)
    assert "30 minutes" in render_email_subject(sub)


def test_subject_contains_stage():
    sub = make_subscription(stage="Green Stage")
    assert "Green Stage" in render_email_subject(sub)


# ---------------------------------------------------------------------------
# Plain-text body tests
# ---------------------------------------------------------------------------

def test_text_body_contains_artist():
    sub = make_subscription(artist="IU")
    assert "IU" in render_email_text(sub)


def test_text_body_contains_stage():
    sub = make_subscription(stage="Green Stage")
    assert "Green Stage" in render_email_text(sub)


def test_text_body_contains_time():
    sub = make_subscription(performance_dt=datetime(2026, 8, 15, 11, 0))
    assert "11:00" in render_email_text(sub)


def test_text_body_contains_minutes():
    sub = make_subscription(notify_minutes=20)
    assert "20 minutes" in render_email_text(sub)


# ---------------------------------------------------------------------------
# HTML body tests
# ---------------------------------------------------------------------------

def test_html_contains_artist():
    sub = make_subscription(artist="aespa")
    assert "aespa" in render_email_html(sub)


def test_html_contains_stage():
    sub = make_subscription(stage="Main Stage")
    assert "Main Stage" in render_email_html(sub)


def test_html_contains_time():
    sub = make_subscription(performance_dt=datetime(2026, 8, 15, 20, 30))
    assert "20:30" in render_email_html(sub)


def test_html_is_valid_html():
    sub = make_subscription()
    html = render_email_html(sub)
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html


# ---------------------------------------------------------------------------
# Send function tests
# ---------------------------------------------------------------------------

def test_send_calls_smtp(monkeypatch):
    sub = make_subscription()
    mock_smtp = MagicMock()

    with patch("email_sender.smtplib.SMTP", return_value=mock_smtp):
        monkeypatch.setattr("config.SMTP_USE_TLS", True)
        monkeypatch.setattr("config.SMTP_USER", "user@example.com")
        monkeypatch.setattr("config.SMTP_PASSWORD", "secret")
        send_notification_email(sub)

    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once()
    mock_smtp.sendmail.assert_called_once()
    mock_smtp.quit.assert_called_once()


def test_send_raises_email_send_error_on_smtp_failure():
    sub = make_subscription()

    with patch("email_sender.smtplib.SMTP", side_effect=ConnectionRefusedError("no server")):
        with pytest.raises(EmailSendError):
            send_notification_email(sub)
