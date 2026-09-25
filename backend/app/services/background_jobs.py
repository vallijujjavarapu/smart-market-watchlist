import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import POLL_INTERVAL_SECONDS
from app.database import SessionLocal
from app.models import WatchlistItem
from app.services.market_data import ingest_snapshots, ensure_ticker_meta

logger = logging.getLogger("background_jobs")
scheduler = BackgroundScheduler()


def poll_all_tracked_tickers():
    """Runs on a fixed interval. Pulls the DISTINCT set of tickers across all
    users' watchlists and fetches each once, no matter how many users track
    it. This is the core scaling decision: cost grows with unique tickers,
    not with users."""
    db = SessionLocal()
    try:
        tickers = [row[0] for row in db.query(WatchlistItem.ticker).distinct().all()]
        if not tickers:
            return
        for ticker in tickers:
            ensure_ticker_meta(db, ticker)
        written = ingest_snapshots(db, tickers)
        logger.info(f"Polled {len(tickers)} tickers, wrote {written} snapshots.")
    except Exception as e:
        logger.exception(f"Polling cycle failed: {e}")
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            poll_all_tracked_tickers,
            "interval",
            seconds=POLL_INTERVAL_SECONDS,
            id="poll_prices",
            next_run_time=None,  # first run scheduled immediately below
        )
        scheduler.start()
        # Kick off an immediate first poll so the app has data right away
        poll_all_tracked_tickers()
        logger.info(f"Scheduler started, polling every {POLL_INTERVAL_SECONDS}s.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
