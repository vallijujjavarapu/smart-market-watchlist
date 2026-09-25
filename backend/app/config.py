import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/watchlist.db")

# --- Market data polling ---
# How often the background job refreshes prices for all tracked tickers (seconds)
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))  # 5 min

# How many days of snapshot history we keep per ticker for volatility calcs
VOLATILITY_LOOKBACK_DAYS = int(os.getenv("VOLATILITY_LOOKBACK_DAYS", "30"))

# EWMA smoothing factor (lambda). Higher = more weight on recent moves.
EWMA_LAMBDA = float(os.getenv("EWMA_LAMBDA", "0.94"))  # RiskMetrics standard

# Significance thresholds
Z_SCORE_ALERT_THRESHOLD = float(os.getenv("Z_SCORE_ALERT_THRESHOLD", "1.5"))
VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.0"))

# How stale a snapshot can be before we flag it in the API response (seconds)
STALE_DATA_THRESHOLD_SECONDS = int(os.getenv("STALE_DATA_THRESHOLD_SECONDS", "900"))  # 15 min

# Data source (for now: yfinance). Kept as a config value so swapping providers
# later (Finnhub, Alpha Vantage, a real NSE feed) doesn't touch business logic.
MARKET_DATA_PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "yfinance")
