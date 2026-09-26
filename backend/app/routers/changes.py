from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import VOLATILITY_LOOKBACK_DAYS, STALE_DATA_THRESHOLD_SECONDS
from app.database import get_db
from app.deps import get_current_user
from app.models import User, WatchlistItem, PriceSnapshot, TickerMeta, UserTickerState, SignalEvent
from app.schemas import (
    TickerChangeOut, SignalDetail, WatchlistChangesResponse, MarkSeenRequest,
)
from app.services.significance import evaluate_ticker

router = APIRouter(prefix="/watchlist", tags=["changes"])


def _price_history(db: Session, ticker: str, since: datetime):
    rows = (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.ticker == ticker, PriceSnapshot.timestamp >= since)
        .order_by(PriceSnapshot.timestamp.asc())
        .all()
    )
    return rows


def _sector_price_series(db: Session, sector: str, exclude_ticker: str, since: datetime) -> Optional[List[float]]:
    """Approximate a 'sector index' as the average price return of other
    tracked tickers in the same sector. This is a simplification - a real
    system would use an actual sector index/ETF feed - but it's a defensible
    stand-in that needs no extra external data source, and we say so plainly
    here rather than pretending it's more than it is."""
    peers = (
        db.query(TickerMeta.ticker)
        .filter(TickerMeta.sector == sector, TickerMeta.ticker != exclude_ticker)
        .all()
    )
    peer_tickers = [p[0] for p in peers]
    if not peer_tickers:
        return None

    series_by_ticker = {}
    for peer in peer_tickers:
        history = _price_history(db, peer, since)
        if len(history) >= 2:
            series_by_ticker[peer] = [h.price for h in history]

    if not series_by_ticker:
        return None

    # Align on shortest series length, average normalized returns per step
    min_len = min(len(v) for v in series_by_ticker.values())
    if min_len < 2:
        return None
    averaged = []
    for i in range(min_len):
        point_avg = sum(series_by_ticker[t][i] / series_by_ticker[t][0] for t in series_by_ticker) / len(series_by_ticker)
        averaged.append(point_avg)
    return averaged


@router.get("/changes", response_model=WatchlistChangesResponse)
def get_changes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
    now = datetime.utcnow()
    since = now - timedelta(days=VOLATILITY_LOOKBACK_DAYS)

    states_by_ticker: Dict[str, UserTickerState] = {
        s.ticker: s
        for s in db.query(UserTickerState).filter(UserTickerState.user_id == user.id).all()
    }

    attention_needed: List[TickerChangeOut] = []
    quiet: List[TickerChangeOut] = []

    for item in items:
        ticker = item.ticker
        history = _price_history(db, ticker, since)
        if not history:
            continue  # no data yet (e.g. just added, first poll hasn't run)

        latest = history[-1]
        prices = [h.price for h in history]
        volumes = [h.volume for h in history]

        meta = db.query(TickerMeta).filter(TickerMeta.ticker == ticker).first()
        sector_series = None
        if meta and meta.sector:
            sector_series = _sector_price_series(db, meta.sector, ticker, since)

        attention_score, signals, verdict = evaluate_ticker(
            prices, volumes, sector_prices=sector_series, sensitivity=item.sensitivity
        )

        # Persist notable signals so they're queryable later (history, "why" tooltip)
        for s in signals:
            db.add(SignalEvent(
                ticker=ticker, signal_type=s.signal_type, score=s.score, z_score=s.z_score,
                details=s.message,
            ))

        state = states_by_ticker.get(ticker)
        last_seen_price = state.last_seen_price if state else None
        last_seen_at = state.last_seen_at if state else None
        change_since_seen = None
        change_pct_since_seen = None
        if last_seen_price:
            change_since_seen = latest.price - last_seen_price
            change_pct_since_seen = (change_since_seen / last_seen_price * 100) if last_seen_price else None

        is_stale = bool(latest.is_stale) or (now - latest.timestamp).total_seconds() > STALE_DATA_THRESHOLD_SECONDS

        out = TickerChangeOut(
            ticker=ticker,
            current_price=latest.price,
            current_volume=latest.volume,
            as_of=latest.timestamp,
            is_stale=is_stale,
            last_seen_price=last_seen_price,
            last_seen_at=last_seen_at,
            price_change_since_last_seen=change_since_seen,
            price_change_pct_since_last_seen=change_pct_since_seen,
            attention_score=attention_score,
            signals=[SignalDetail(signal_type=s.signal_type, score=s.score, z_score=s.z_score, message=s.message) for s in signals],
            verdict=verdict,
        )

        (attention_needed if attention_score >= 40 else quiet).append(out)

    db.commit()

    attention_needed.sort(key=lambda t: t.attention_score, reverse=True)
    quiet.sort(key=lambda t: t.ticker)

    return WatchlistChangesResponse(generated_at=now, attention_needed=attention_needed, quiet=quiet)


@router.post("/mark-seen", status_code=204)
def mark_seen(
    payload: MarkSeenRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Snapshot 'what the user just saw' into server-side state. This is what
    makes 'what changed since I last checked' work across sessions and
    devices - the diff baseline lives in the DB, not in browser storage."""
    now = datetime.utcnow()
    tickers = payload.tickers
    items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id)
    if tickers:
        items = items.filter(WatchlistItem.ticker.in_([t.upper() for t in tickers]))
    items = items.all()

    for item in items:
        latest = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.ticker == item.ticker)
            .order_by(PriceSnapshot.timestamp.desc())
            .first()
        )
        if not latest:
            continue

        state = (
            db.query(UserTickerState)
            .filter(UserTickerState.user_id == user.id, UserTickerState.ticker == item.ticker)
            .first()
        )
        if not state:
            state = UserTickerState(user_id=user.id, ticker=item.ticker)
            db.add(state)

        state.last_seen_price = latest.price
        state.last_seen_volume = latest.volume
        state.last_seen_at = now

    db.commit()
    return None
