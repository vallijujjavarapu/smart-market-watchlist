from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# ---------- Watchlist management ----------

class WatchlistItemCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    sensitivity: float = Field(1.0, gt=0, le=3.0, description="Lower = alert on smaller moves")


class WatchlistItemOut(BaseModel):
    id: int
    ticker: str
    added_at: datetime
    sensitivity: float

    class Config:
        from_attributes = True


class WatchlistItemUpdate(BaseModel):
    sensitivity: float = Field(..., gt=0, le=3.0)


# ---------- Signals / "what changed" ----------

class SignalDetail(BaseModel):
    signal_type: str
    score: float
    z_score: Optional[float] = None
    message: str


class TickerChangeOut(BaseModel):
    ticker: str
    current_price: float
    current_volume: Optional[int] = None
    as_of: datetime
    is_stale: bool

    last_seen_price: Optional[float] = None
    last_seen_at: Optional[datetime] = None
    price_change_since_last_seen: Optional[float] = None
    price_change_pct_since_last_seen: Optional[float] = None

    attention_score: float
    signals: List[SignalDetail] = []
    verdict: str  # plain-language summary


class WatchlistChangesResponse(BaseModel):
    generated_at: datetime
    attention_needed: List[TickerChangeOut]
    quiet: List[TickerChangeOut]


class MarkSeenRequest(BaseModel):
    tickers: Optional[List[str]] = None  # None = mark entire watchlist as seen
