import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config
from models import Subscription


class EmailSendError(Exception):
    pass


def render_email_subject(sub: Subscription) -> str:
    return f"Reminder: {sub.artist} starts in {sub.notify_minutes} minutes at {sub.stage}"


def render_email_text(sub: Subscription) -> str:
    local_time = sub.performance_dt.strftime("%H:%M")
    return (
        f"FESTIVAL REMINDER\n"
        f"{'=' * 40}\n\n"
        f"  {sub.artist}\n"
        f"  {sub.stage}\n"
        f"  Starts at {local_time}\n\n"
        f"  You have {sub.notify_minutes} minutes — head there now!\n\n"
        f"{'=' * 40}\n"
        f"You subscribed to this reminder via Festival Timetable Reminder.\n"
    )


def render_email_html(sub: Subscription) -> str:
    local_time = sub.performance_dt.strftime("%H:%M")
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: system-ui, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .card {{ background: white; border-radius: 12px; padding: 32px; max-width: 480px; margin: 0 auto; }}
    .label {{ font-size: 11px; font-weight: 600; letter-spacing: 0.1em; color: #888; text-transform: uppercase; }}
    .artist {{ font-size: 28px; font-weight: 700; color: #111; margin: 8px 0; }}
    .stage {{ font-size: 16px; color: #555; margin-bottom: 24px; }}
    .time-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }}
    .time {{ font-size: 36px; font-weight: 700; color: #111; }}
    .cta {{ background: #111; color: white; padding: 14px 24px; border-radius: 8px;
             font-size: 16px; font-weight: 600; text-align: center; }}
    .footer {{ margin-top: 24px; font-size: 12px; color: #aaa; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="label">Festival Reminder</div>
    <div class="artist">{sub.artist}</div>
    <div class="stage">{sub.stage}</div>
    <div class="time-row">
      <div class="time">{local_time}</div>
    </div>
    <div class="cta">You have {sub.notify_minutes} minutes — head there now!</div>
    <div class="footer">
      You subscribed to this reminder via Festival Timetable Reminder.
    </div>
  </div>
</body>
</html>"""


def send_notification_email(sub: Subscription) -> None:
    """Send reminder email via SMTP. Raises EmailSendError on failure."""
    subject = render_email_subject(sub)
    text_body = render_email_text(sub)
    html_body = render_email_html(sub)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = sub.email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if config.SMTP_USE_TLS:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)

        if config.SMTP_USER:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)

        server.sendmail(config.EMAIL_FROM, sub.email, msg.as_string())
        server.quit()
    except Exception as e:
        raise EmailSendError(f"Failed to send email to {sub.email}: {e}") from e
