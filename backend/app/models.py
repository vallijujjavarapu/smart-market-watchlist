from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, Index, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)

    watchlist_items = relationship("WatchlistItem", back_populates="user", cascade="all, delete-orphan")
    ticker_states = relationship("UserTickerState", back_populates="user", cascade="all, delete-orphan")


class TickerMeta(Base):
    """Static/slow-changing info about a ticker. Cached separately from live
    prices so we're not re-fetching name/sector on every poll."""
    __tablename__ = "ticker_meta"

    ticker = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    sector = Column(String, nullable=True, index=True)
    exchange = Column(String, nullable=True)
    last_updated = Column(DateTime, default=utcnow, onupdate=utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False, index=True)
    added_at = Column(DateTime, default=utcnow)

    # Per-stock sensitivity: lower = alert on smaller moves. Default 1.0 = use
    # global thresholds untouched. This is the personalization knob.
    sensitivity = Column(Float, default=1.0, nullable=False)

    user = relationship("User", back_populates="watchlist_items")

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_user_ticker"),
    )


class PriceSnapshot(Base):
    """A single price observation for a ticker at a point in time.
    This is the append-only time series everything else is computed from."""
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=utcnow, index=True)
    source = Column(String, default="yfinance")
    is_stale = Column(Integer, default=0)  # 1 if served from cache due to fetch failure

    __table_args__ = (
        # Prevents duplicate ingestion if a poll retries after a partial failure
        UniqueConstraint("ticker", "timestamp", name="uq_ticker_timestamp"),
        Index("ix_ticker_timestamp_desc", "ticker", "timestamp"),
    )


class UserTickerState(Base):
    """What a specific user last saw for a specific ticker. This is what makes
    'what changed since I last checked' a real, server-side, cross-device
    concept instead of something derived from 'today's change'."""
    __tablename__ = "user_ticker_state"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False, index=True)

    last_seen_price = Column(Float, nullable=True)
    last_seen_volume = Column(Integer, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="ticker_states")

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_user_ticker_state"),
    )


class SignalEvent(Base):
    """A computed, timestamped record of 'something notable happened' for a
    ticker. Stored (not just computed on the fly) so we can: show history,
    power the 'explain this signal' UI, and later learn from which signals
    users actually engage with."""
    __tablename__ = "signal_events"

    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=utcnow, index=True)

    signal_type = Column(String, nullable=False)  # price_shock | volume_anomaly | trend_break | relative_move
    score = Column(Float, nullable=False)  # 0-100 attention score contribution
    z_score = Column(Float, nullable=True)
    details = Column(Text, nullable=True)  # JSON-encoded supporting numbers, for the "why" tooltip

    __table_args__ = (
        Index("ix_signal_ticker_timestamp", "ticker", "timestamp"),
    )
