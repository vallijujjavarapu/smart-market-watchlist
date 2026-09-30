import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, engine, SessionLocal
from app.models import User, WatchlistItem, PriceSnapshot, TickerMeta

email = sys.argv[1] if len(sys.argv) > 1 else "you@test.com"
random.seed(7)

N = 40  # hourly points

# (ticker, normal noise, final move, final volume multiplier)
DEMOS = [
    ("SPIKECO", 0.002, 0.06, 3.5),   # big price shock + volume spike
    ("DRIFTCO", 0.003, 0.012, 1.0),  # moderate move
    ("CALMCO", 0.002, 0.0005, 1.0),  # nothing happening
]

Base.metadata.create_all(bind=engine)
db = SessionLocal()

user = db.query(User).filter(User.email == email).first()
if not user:
    user = User(email=email)
    db.add(user)
    db.commit()
    db.refresh(user)

now = datetime.utcnow()

for ticker, noise, last_move, vol_mult in DEMOS:
    db.query(PriceSnapshot).filter(PriceSnapshot.ticker == ticker).delete()

    prices = [100.0]
    for _ in range(N - 2):
        prices.append(prices[-1] * (1 + random.gauss(0, noise)))
    prices.append(prices[-1] * (1 + last_move))

    for i, p in enumerate(prices):
        ts = now - timedelta(hours=(N - 1 - i), minutes=1)
        vol = int(1_000_000 * random.uniform(0.9, 1.1))
        if i == N - 1:
            vol = int(1_000_000 * vol_mult)
        db.add(PriceSnapshot(ticker=ticker, price=round(p, 2), volume=vol, timestamp=ts))

    if not db.query(TickerMeta).filter(TickerMeta.ticker == ticker).first():
        db.add(TickerMeta(ticker=ticker, name=ticker, sector=None))

    exists = db.query(WatchlistItem).filter(
        WatchlistItem.user_id == user.id, WatchlistItem.ticker == ticker
    ).first()
    if not exists:
        db.add(WatchlistItem(user_id=user.id, ticker=ticker, sensitivity=1.0))

db.commit()
print(f"Seeded {len(DEMOS)} demo tickers for {email}")