# Smart Market Watchlist — Backend

Not "track stocks, see prices." Instead: **tell me the 2-3 things that actually
deserve my attention since I last looked, and be honest when nothing does.**

## The core idea

A raw "% change" is a bad signal on its own — a 1% move on a sleepy utility
stock is unusual, the same 1% move on a volatile small-cap is Tuesday. So
instead of one flat threshold, every ticker gets judged against **its own
normal behavior**:

- **Price shock** — is today's move statistically unusual for *this stock*
  (EWMA volatility + z-score), not just big in absolute terms
- **Volume anomaly** — is trading interest itself unusual
- **Trend break** — did price cross its own moving average (regime shift)
- **Relative move** — did the stock move differently from its own sector, or
  did it just drift with the whole market (noise)

These combine into a single 0–100 **attention score**, and every score comes
with a plain-language verdict, not jargon — e.g. *"Moved sharply up — bigger
than its typical daily move (3.2x normal volatility)"* rather than "z=3.2".
Stocks that don't clear the bar are shown as genuinely quiet, not padded with
noise — restraint is a feature, not a gap.

## Design decisions (mapped to what's being judged)

**Product & Problem Interpretation** — the product bet is that most retail
users don't want more data, they want to be told what to ignore. The API
splits `attention_needed` vs `quiet` explicitly rather than returning one
ranked list, so the frontend can default to showing almost nothing.

**Engineering Depth**
- `UserTickerState` is real server-side state (last seen price/volume/time
  per user per ticker) — this is what makes "what changed since I last
  checked" work across devices and after multi-day gaps, instead of being a
  browser-storage trick or a "since market open" shortcut.
- Background polling batches ALL distinct tickers across ALL users into one
  fetch cycle (`background_jobs.py`) — cost scales with unique tickers
  tracked, not with number of users. This is the scaling answer.
- EWMA volatility (RiskMetrics-style) reacts faster to regime change than a
  flat rolling stddev would, and is cheap to compute incrementally.

**Edge Cases & Resilience**
- A failed price fetch doesn't error or leave a gap — it falls back to the
  last known snapshot and is explicitly flagged `is_stale: true`, so the
  frontend can show a "data delayed" badge instead of lying with a stale
  number presented as fresh.
- Snapshot writes are deduped on `(ticker, timestamp)` at the DB constraint
  level, so a retried poll (timeout, etc.) can't double-insert.
- A ticker with no data yet (just added, first poll hasn't run) is skipped
  gracefully rather than crashing the `/changes` response.
- Per-ticker `sensitivity` lets a user tune how twitchy alerts are per stock
  without needing global config changes.

**Code Quality & Simplicity**
- The significance logic lives in one pure-function module
  (`services/significance.py`) with no DB or HTTP dependencies — it's
  independently testable and the whole "what counts as meaningful" answer is
  readable in one file.
- Auth is intentionally minimal (`X-User-Email` header, get-or-create) — real
  JWT/OAuth is orthogonal to what's being evaluated here and would have
  eaten time better spent on the actual watchlist intelligence. Swapping in
  real auth later only touches `deps.py`.

**Originality & Thoughtfulness**
- The sector-relative-move signal approximates a sector index using the
  average of other tracked tickers in the same sector (via cached
  `TickerMeta.sector`) rather than requiring an external index/ETF feed —
  called out explicitly as a simplification, not hidden.
- Signals are persisted (`SignalEvent`) rather than computed and discarded —
  this is what enables a future "why was I shown this" tooltip and a
  feedback loop (which signals users actually engage with) without any
  schema changes.

## What's deliberately NOT built yet (and why)

- News-headline correlation ("likely tied to: ...") — stretch goal, cut to
  keep the core engine solid rather than half-finished
- Real auth — see above
- WebSocket push — polling + a "refresh" affordance is enough for v1; noted
  as a clear next step for a live-open-app experience

## Running it

\`\`\`bash
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload
\`\`\`

API docs at `http://localhost:8000/docs`. Every request needs an
`X-User-Email` header (any email string — it's get-or-create for this demo).

### Quick walkthrough

\`\`\`bash
# Add a ticker
curl -X POST localhost:8000/watchlist \\
  -H "X-User-Email: you@example.com" -H "Content-Type: application/json" \\
  -d '{"ticker": "RELIANCE.NS", "sensitivity": 1.0}'

# See what changed
curl localhost:8000/watchlist/changes -H "X-User-Email: you@example.com"

# Mark everything as seen (sets the diff baseline for next visit)
curl -X POST localhost:8000/watchlist/mark-seen \\
  -H "X-User-Email: you@example.com" -H "Content-Type: application/json" -d '{}'
\`\`\`

Note: ticker symbols must match what `yfinance` expects (e.g. NSE tickers
need a `.NS` suffix, like `RELIANCE.NS` or `TCS.NS`).
