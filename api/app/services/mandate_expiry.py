from datetime import UTC, datetime, timedelta

from app.config import settings


def is_expired(created_at: datetime) -> bool:
    """No expires_at column — the TTL is a global constant, not per-mandate,
    so it's cheaper and just as correct to compute from created_at."""
    return datetime.now(UTC) > created_at + timedelta(minutes=settings.intent_expiry_minutes)
