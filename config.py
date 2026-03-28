import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
EMAIL_SENDER           = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD         = os.getenv("EMAIL_PASSWORD", "")
SMTP_HOST              = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT              = int(os.getenv("SMTP_PORT", "587"))
SECRET_KEY             = os.getenv("SECRET_KEY", "change-me")
DATABASE_URL           = os.getenv("DATABASE_URL", "sqlite:///investor_digest.db")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
SEC_USER_AGENT         = os.getenv("SEC_USER_AGENT", f"InvestorDigest {EMAIL_SENDER}")
APP_NAME               = os.getenv("APP_NAME", "Investor Digest")
FILING_TYPES           = ["10-K", "10-Q", "8-K", "6-K", "20-F"]
