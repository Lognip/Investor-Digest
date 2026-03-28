"""Database models — Users, Holdings, FilingSummaries."""

import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name          = db.Column(db.String(100), default="")
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Email preferences
    digest_email  = db.Column(db.String(255), default="")   # where to send digests
    notify_on_8k  = db.Column(db.Boolean, default=True)
    notify_on_10k = db.Column(db.Boolean, default=True)
    notify_on_10q = db.Column(db.Boolean, default=True)

    holdings  = db.relationship("Holding", backref="user",
                                lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def digest_address(self):
        return self.digest_email or self.email


class Holding(db.Model):
    __tablename__ = "holdings"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker       = db.Column(db.String(10), nullable=False)
    company      = db.Column(db.String(200), default="")
    added_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_checked = db.Column(db.String(10), default="2024-01-01")   # YYYY-MM-DD

    summaries = db.relationship("FilingSummary", backref="holding",
                                lazy=True, cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("user_id", "ticker", name="uq_user_ticker"),
    )

    def to_dict(self):
        return {
            "id": self.id, "ticker": self.ticker,
            "company": self.company, "last_checked": self.last_checked,
        }


class FilingSummary(db.Model):
    __tablename__ = "filing_summaries"

    id               = db.Column(db.Integer, primary_key=True)
    holding_id       = db.Column(db.Integer, db.ForeignKey("holdings.id"), nullable=False)
    ticker           = db.Column(db.String(10), nullable=False)
    company          = db.Column(db.String(200), default="")
    form_type        = db.Column(db.String(20), nullable=False)
    filed_date       = db.Column(db.String(10), nullable=False)
    accession_number = db.Column(db.String(50), nullable=False)
    document_url     = db.Column(db.Text, default="")
    headline         = db.Column(db.Text, default="")
    key_points       = db.Column(db.Text, default="[]")   # JSON
    financials       = db.Column(db.Text, default="")
    risks            = db.Column(db.Text, default="")
    outlook          = db.Column(db.Text, default="")
    sentiment        = db.Column(db.String(20), default="Neutral")
    action_items     = db.Column(db.Text, default="")
    raw_summary      = db.Column(db.Text, default="")
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    emailed          = db.Column(db.Boolean, default=False)

    def to_dict(self):
        try:
            kp = json.loads(self.key_points) if self.key_points else []
        except Exception:
            kp = []
        return {
            "id": self.id, "ticker": self.ticker, "company": self.company,
            "form": self.form_type, "filed": self.filed_date,
            "accession_number": self.accession_number,
            "document_url": self.document_url, "headline": self.headline,
            "key_points": kp, "financials": self.financials,
            "risks": self.risks, "outlook": self.outlook,
            "sentiment": self.sentiment, "action_items": self.action_items,
            "raw_summary": self.raw_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "emailed": self.emailed,
        }
