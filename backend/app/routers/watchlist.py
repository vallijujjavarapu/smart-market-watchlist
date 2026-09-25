from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, WatchlistItem
from app.schemas import WatchlistItemCreate, WatchlistItemOut, WatchlistItemUpdate
from app.services.market_data import ensure_ticker_meta

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=List[WatchlistItemOut])
def get_watchlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()


@router.post("", response_model=WatchlistItemOut, status_code=201)
def add_ticker(
    payload: WatchlistItemCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticker = payload.ticker.strip().upper()

    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.ticker == ticker)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"{ticker} is already on your watchlist")

    item = WatchlistItem(user_id=user.id, ticker=ticker, sensitivity=payload.sensitivity)
    db.add(item)
    db.commit()
    db.refresh(item)

    # Warm the ticker_meta cache immediately so the first /changes call has
    # sector info available for the relative-move signal, and trigger a
    # first snapshot fetch on next poll cycle automatically (ticker is now
    # in the distinct set the background job queries).
    ensure_ticker_meta(db, ticker)

    return item


@router.patch("/{ticker}", response_model=WatchlistItemOut)
def update_sensitivity(
    ticker: str,
    payload: WatchlistItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.ticker == ticker.upper())
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"{ticker} is not on your watchlist")
    item.sensitivity = payload.sensitivity
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{ticker}", status_code=204)
def remove_ticker(
    ticker: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.ticker == ticker.upper())
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"{ticker} is not on your watchlist")
    db.delete(item)
    db.commit()
    return None
