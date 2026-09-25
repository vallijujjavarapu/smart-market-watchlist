"""
Minimal user identification for hackathon scope.

We deliberately did NOT build full auth (JWT/OAuth) here - it's orthogonal to
what's being evaluated (the watchlist intelligence itself) and would eat time
better spent on the significance engine. Instead: a client sends an
`X-User-Email` header, and we get-or-create that user. This still gives us
real per-user, server-side state (the actual requirement - cross-device
persistence), and swapping in real auth later only means changing this one
function, not the rest of the app.
"""
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


def get_current_user(
    x_user_email: str = Header(..., description="Identifies the user; get-or-create for this demo"),
    db: Session = Depends(get_db),
) -> User:
    if not x_user_email or "@" not in x_user_email:
        raise HTTPException(status_code=400, detail="X-User-Email header is required")

    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        user = User(email=x_user_email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
