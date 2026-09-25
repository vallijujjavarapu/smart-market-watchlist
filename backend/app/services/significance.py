"""
Significance engine.

Core idea: a raw % price change means very little on its own. A 1% move in a
sleepy utility stock is unusual; a 1% move in a volatile small-cap is Tuesday.
So instead of a flat "> X% = alert" rule, we ask: is this move unusual
*for this specific stock*, given how it normally behaves?

We compute:
  1. EWMA volatility  -> a fast-reacting estimate of "normal" daily move size
  2. Z-score           -> how many "normal moves" today's move represents
  3. Volume anomaly    -> is trading volume itself unusual
  4. Relative move     -> did the stock move differently from its own sector
                          (a 2% move on a day the whole sector is up 2% is
                          noise; the same move on a flat sector day is signal)

Each check produces a SignalDetail with a score contribution (0-100). We sum
and cap at 100 to get a single attention_score used for sorting the feed.
"""
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.config import EWMA_LAMBDA, Z_SCORE_ALERT_THRESHOLD, VOLUME_SPIKE_MULTIPLIER


@dataclass
class PricePoint:
    price: float
    volume: Optional[int]


@dataclass
class SignalResult:
    signal_type: str
    score: float
    z_score: Optional[float]
    message: str


def compute_returns(prices: Sequence[float]) -> List[float]:
    """Simple period-over-period returns from a price series, oldest first."""
    returns = []
    for i in range(1, len(prices)):
        prev, curr = prices[i - 1], prices[i]
        if prev > 0:
            returns.append((curr - prev) / prev)
    return returns


def ewma_volatility(returns: Sequence[float], lam: float = EWMA_LAMBDA) -> Optional[float]:
    """RiskMetrics-style exponentially weighted moving average volatility.
    Weights recent returns more heavily than old ones, so it reacts faster to
    a change in market regime than a flat rolling stddev would.

    variance_t = lam * variance_(t-1) + (1 - lam) * return_t^2
    """
    if len(returns) < 2:
        return None
    variance = returns[0] ** 2
    for r in returns[1:]:
        variance = lam * variance + (1 - lam) * (r ** 2)
    return math.sqrt(variance) if variance > 0 else None


def z_score_for_latest_move(prices: Sequence[float]) -> Optional[float]:
    """How many EWMA-volatility-units was the most recent move?"""
    if len(prices) < 3:
        return None
    returns = compute_returns(prices)
    if len(returns) < 2:
        return None
    latest_return = returns[-1]
    # Volatility estimated on all returns *excluding* the latest one, so we're
    # asking "was today's move unusual relative to history", not relative to
    # a baseline that already includes today.
    vol = ewma_volatility(returns[:-1])
    if not vol or vol == 0:
        return None
    return latest_return / vol


def volume_anomaly_ratio(volumes: Sequence[int]) -> Optional[float]:
    """Latest volume vs the average of prior volumes."""
    valid = [v for v in volumes if v is not None and v > 0]
    if len(valid) < 3:
        return None
    *history, latest = valid
    avg_history = sum(history) / len(history)
    if avg_history == 0:
        return None
    return latest / avg_history


def evaluate_price_shock(prices: Sequence[float], sensitivity: float = 1.0) -> Optional[SignalResult]:
    z = z_score_for_latest_move(prices)
    if z is None:
        return None
    threshold = Z_SCORE_ALERT_THRESHOLD / max(sensitivity, 0.1)
    if abs(z) < threshold:
        return None
    direction = "up" if z > 0 else "down"
    magnitude = "sharply" if abs(z) >= threshold * 1.5 else "notably"
    score = min(100.0, 40 + abs(z) * 15)
    pct = (prices[-1] - prices[-2]) / prices[-2] * 100 if prices[-2] else 0
    return SignalResult(
        signal_type="price_shock",
        score=score,
        z_score=z,
        message=(
            f"Moved {magnitude} {direction} ({pct:+.2f}%) \u2014 bigger than its "
            f"typical daily move ({abs(z):.1f}x normal volatility)."
        ),
    )


def evaluate_volume_anomaly(volumes: Sequence[int], sensitivity: float = 1.0) -> Optional[SignalResult]:
    ratio = volume_anomaly_ratio(volumes)
    if ratio is None:
        return None
    threshold = VOLUME_SPIKE_MULTIPLIER / max(sensitivity, 0.1)
    if ratio < threshold:
        return None
    score = min(100.0, 30 + (ratio - threshold) * 10)
    return SignalResult(
        signal_type="volume_anomaly",
        score=score,
        z_score=None,
        message=f"Trading volume is {ratio:.1f}x its recent average \u2014 unusual interest today.",
    )


def evaluate_relative_move(
    stock_prices: Sequence[float],
    sector_prices: Sequence[float],
    sensitivity: float = 1.0,
) -> Optional[SignalResult]:
    """Did the stock move differently from its own sector? A move that's just
    the whole sector moving together is market noise, not stock-specific news."""
    if len(stock_prices) < 2 or len(sector_prices) < 2:
        return None
    stock_return = (stock_prices[-1] - stock_prices[-2]) / stock_prices[-2]
    sector_return = (sector_prices[-1] - sector_prices[-2]) / sector_prices[-2]
    divergence = stock_return - sector_return

    threshold = 0.015 / max(sensitivity, 0.1)  # 1.5% divergence baseline
    if abs(divergence) < threshold:
        return None

    direction = "outperformed" if divergence > 0 else "underperformed"
    score = min(100.0, 25 + abs(divergence) * 1000)
    return SignalResult(
        signal_type="relative_move",
        score=score,
        z_score=None,
        message=(
            f"{direction.capitalize()} its sector by {abs(divergence) * 100:.1f} pts today \u2014 "
            f"this looks stock-specific, not just the market moving."
        ),
    )


def evaluate_trend_break(prices: Sequence[float], window: int = 20) -> Optional[SignalResult]:
    """Did price cross its own moving average? Simple, but a genuinely useful
    'regime change' signal that's cheap to compute."""
    if len(prices) < window + 2:
        return None
    ma_before = sum(prices[-window - 1:-1]) / window
    ma_now = sum(prices[-window:]) / window
    prev_price, curr_price = prices[-2], prices[-1]

    crossed_up = prev_price < ma_before and curr_price > ma_now
    crossed_down = prev_price > ma_before and curr_price < ma_now
    if not (crossed_up or crossed_down):
        return None

    direction = "above" if crossed_up else "below"
    return SignalResult(
        signal_type="trend_break",
        score=35.0,
        z_score=None,
        message=f"Just crossed {direction} its {window}-period moving average \u2014 possible trend shift.",
    )


def build_verdict(signals: List[SignalResult], attention_score: float) -> str:
    """Plain-language, non-jargon summary for the UI card."""
    if not signals:
        return "Quiet day \u2014 nothing here clears your attention threshold."
    if attention_score >= 70:
        lead = signals[0]
        return f"Worth a look: {lead.message}"
    if attention_score >= 40:
        return "A modest but real move \u2014 not urgent, but noted."
    return "Minor move \u2014 within normal range."


def evaluate_ticker(
    prices: Sequence[float],
    volumes: Sequence[Optional[int]],
    sector_prices: Optional[Sequence[float]] = None,
    sensitivity: float = 1.0,
) -> tuple[float, List[SignalResult], str]:
    """Run all checks for one ticker and return (attention_score, signals, verdict)."""
    signals: List[SignalResult] = []

    for evaluator, args in [
        (evaluate_price_shock, (prices, sensitivity)),
        (evaluate_volume_anomaly, (volumes, sensitivity)),
        (evaluate_trend_break, (prices,)),
    ]:
        result = evaluator(*args)
        if result:
            signals.append(result)

    if sector_prices:
        rel = evaluate_relative_move(prices, sector_prices, sensitivity)
        if rel:
            signals.append(rel)

    signals.sort(key=lambda s: s.score, reverse=True)
    attention_score = min(100.0, sum(s.score for s in signals) * 0.7) if signals else 0.0
    verdict = build_verdict(signals, attention_score)
    return attention_score, signals, verdict
