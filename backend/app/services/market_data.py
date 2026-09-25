"""
Market data ingestion.

Design choices worth calling out:
- We fetch ONCE per polling cycle for the union of all tickers across all
  users, not once per user request. This is what lets the system scale with
  more users without scaling API calls 1:1 with them.
- If a fetch fails for a ticker, we don't throw the whole cycle away or block
  the API. We fall back to the last known snapshot and mark it stale, so the
  frontend can show a "data delayed" badge instead of an error.
- Snapshot writes are deduped on (ticker, timestamp) at the DB level, so a
  retried poll (e.g. after a timeout) can't double-insert.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import yfinance as yf
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PriceSnapshot, TickerMeta

logger = logging.getLogger("market_data")


class FetchResult:
    def __init__(self, ticker: str, price: Optional[float], volume: Optional[int], is_stale: bool):
        self.ticker = ticker
        self.price = price
        self.volume = volume
        self.is_stale = is_stale


def fetch_latest_prices(tickers: List[str]) -> Dict[str, FetchResult]:
    """Batch-fetch current price + volume for a list of tickers.
    One provider call for the whole batch, not one per ticker."""
    results: Dict[str, FetchResult] = {}
    if not tickers:
        return results

    try:
        data = yf.Tickers(" ".join(tickers))
        for ticker in tickers:
            try:
                info = data.tickers[ticker].fast_info
                price = float(info.get("lastPrice")) if info.get("lastPrice") else None
                volume = int(info.get("lastVolume")) if info.get("lastVolume") else None
                if price is None:
                    raise ValueError("no price returned")
                results[ticker] = FetchResult(ticker, price, volume, is_stale=False)
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
                results[ticker] = FetchResult(ticker, None, None, is_stale=True)
    except Exception as e:
        # Whole-batch failure (e.g. network down) - mark everything stale,
        # caller falls back to last-known snapshots for all of them.
        logger.error(f"Batch fetch failed entirely: {e}")
        for ticker in tickers:
            results[ticker] = FetchResult(ticker, None, None, is_stale=True)

    return results


def get_last_known_snapshot(db: Session, ticker: str) -> Optional[PriceSnapshot]:
    return (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.ticker == ticker)
        .order_by(PriceSnapshot.timestamp.desc())
        .first()
    )


def ingest_snapshots(db: Session, tickers: List[str]) -> int:
    """Fetch current data for all tickers and persist snapshots.
    Falls back to marking a synthetic 'stale repeat' snapshot when a live
    fetch fails, so downstream consumers always have *something* recent to
    read, with an explicit staleness flag rather than a gap or an error."""
    fetched = fetch_latest_prices(tickers)
    now = datetime.now(timezone.utc)
    written = 0

    for ticker in tickers:
        result = fetched.get(ticker)
        price, volume, is_stale = None, None, True

        if result and result.price is not None:
            price, volume, is_stale = result.price, result.volume, False
        else:
            last = get_last_known_snapshot(db, ticker)
            if last:
                price, volume = last.price, last.volume
            else:
                continue  # never had data for this ticker; nothing to fall back to

        snapshot = PriceSnapshot(
            ticker=ticker,
            price=price,
            volume=volume,
            timestamp=now,
            is_stale=1 if is_stale else 0,
        )
        db.add(snapshot)
        try:
            db.flush()
            written += 1
        except IntegrityError:
            db.rollback()  # duplicate (ticker, timestamp) from a retried poll - skip silently

    db.commit()
    return written


def ensure_ticker_meta(db: Session, ticker: str) -> TickerMeta:
    """Cache slow-changing ticker info (name, sector) so we don't hit the
    provider for it on every poll cycle."""
    meta = db.query(TickerMeta).filter(TickerMeta.ticker == ticker).first()
    if meta:
        return meta

    name, sector = ticker, None
    try:
        info = yf.Ticker(ticker).info
        name = info.get("shortName", ticker)
        sector = info.get("sector")
    except Exception as e:
        logger.warning(f"Could not fetch meta for {ticker}: {e}")

    meta = TickerMeta(ticker=ticker, name=name, sector=sector)
    db.add(meta)
    db.commit()
    db.refresh(meta)
    return meta
