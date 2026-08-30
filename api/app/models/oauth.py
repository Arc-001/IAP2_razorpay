import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base
from app.models.mandates import _now


class OAuthRefreshToken(Base):
    """Refresh tokens for the MCP server's OAuth connector flow (see plan
    "Add real OAuth to the MCP server"). Only a SHA-256 hash is ever
    persisted — same discipline services/password.py already applies to
    passwords — so a leaked table row can't be replayed as a live token.
    Authorization codes and pending /oauth/authorize requests are NOT
    persisted here or anywhere: both live seconds, not days, and an
    in-memory store (services/oauth.py) is sufficient — losing one on a
    restart just means the customer retries the connect."""

    __tablename__ = "oauth_refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
