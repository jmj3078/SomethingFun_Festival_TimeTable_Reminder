from os import getenv
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str = getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str   = getenv("GEMINI_MODEL", "gemini-2.5-flash")

DATABASE_URL: str = getenv("DATABASE_URL", "sqlite:///./timetable.db")

SMTP_HOST: str = getenv("SMTP_HOST", "localhost")
SMTP_PORT: int = int(getenv("SMTP_PORT", "587"))
SMTP_USER: str = getenv("SMTP_USER", "")
SMTP_PASSWORD: str = getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS: bool = getenv("SMTP_USE_TLS", "true").lower() == "true"
EMAIL_FROM: str = getenv("EMAIL_FROM", "noreply@festival-reminder.local")

UPLOAD_DIR: str = getenv("UPLOAD_DIR", "./uploads")
MAX_IMAGE_SIZE_MB: int = int(getenv("MAX_IMAGE_SIZE_MB", "10"))
