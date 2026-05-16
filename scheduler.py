import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import sessionmaker

from email_sender import EmailSendError, send_notification_email
from models import Subscription

log = logging.getLogger(__name__)


def check_and_send_notifications(session_factory: sessionmaker) -> int:
    """
    Query subscriptions due for notification and send emails.
    Returns the number of emails successfully sent.
    Called every 60 seconds by the scheduler.
    """
    now_utc = datetime.utcnow()
    sent_count = 0

    with session_factory() as session:
        due = (
            session.query(Subscription)
            .filter(Subscription.sent.is_(False), Subscription.notify_at <= now_utc)
            .all()
        )

        for sub in due:
            try:
                send_notification_email(sub)
                sub.sent = True
                sent_count += 1
                log.info(f"Sent reminder for {sub.artist} to {sub.email}")
            except EmailSendError as e:
                # Keep sent=False so it retries on the next tick
                log.error(f"Email failed for subscription {sub.id}: {e}")

        session.commit()

    return sent_count


def create_scheduler(session_factory: sessionmaker) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=check_and_send_notifications,
        args=[session_factory],
        trigger="interval",
        seconds=60,
        id="notification_checker",
        replace_existing=True,
        misfire_grace_time=30,
    )
    return scheduler
