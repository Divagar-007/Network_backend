# routes/users.py
# User profile read, update, search, and profile-picture upload

import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database.db import get_db
from models.models import User, Connection, ConnectionStatus
from schemas.schemas import UserOut, UserUpdate, UserSummary
from utils.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Current user ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's full profile."""
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update editable profile fields for the authenticated user."""
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=UserOut)
def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload / replace profile picture.
    Accepts JPEG and PNG only. Stores file on disk and saves path in DB.
    """
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WEBP images are allowed")

    # Build a unique filename to avoid collisions
    ext      = file.filename.rsplit(".", 1)[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest     = os.path.join(UPLOAD_DIR, filename)

    with open(dest, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    # Delete old avatar if it exists
    if current_user.profile_picture:
        old = os.path.join(UPLOAD_DIR, os.path.basename(current_user.profile_picture))
        if os.path.exists(old):
            os.remove(old)

    current_user.profile_picture = f"/uploads/{filename}"
    db.commit()
    db.refresh(current_user)
    return current_user


# ── Public profiles ───────────────────────────────────────────────────────────

@router.get("/search", response_model=List[UserSummary])
def search_users(
    q: Optional[str]    = Query(None, description="Search by name, skills, or role"),
    skill: Optional[str] = Query(None),
    role: Optional[str]  = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search users by free-text query (searches name, skills, role),
    or filter explicitly by skill or role.
    """
    query = db.query(User).filter(User.id != current_user.id, User.is_active == True)

    if q:
        like = f"%{q}%"
        query = query.filter(
            User.name.ilike(like) |
            User.skills.ilike(like) |
            User.role.ilike(like)
        )
    if skill:
        query = query.filter(User.skills.ilike(f"%{skill}%"))
    if role:
        query = query.filter(User.role.ilike(f"%{role}%"))

    return query.order_by(User.name).limit(50).all()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Return a user's public profile by ID."""
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Mutual connections ────────────────────────────────────────────────────────

@router.get("/{user_id}/mutual", response_model=List[UserSummary])
def mutual_connections(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return users who are connected to both the current user and the target user."""

    def accepted_ids(uid: int) -> set:
        """Return a set of user IDs that are accepted connections of `uid`."""
        rows = db.query(Connection).filter(
            (
                (Connection.sender_id == uid) |
                (Connection.receiver_id == uid)
            ),
            Connection.status == ConnectionStatus.accepted,
        ).all()
        ids = set()
        for c in rows:
            ids.add(c.receiver_id if c.sender_id == uid else c.sender_id)
        return ids

    my_conns     = accepted_ids(current_user.id)
    their_conns  = accepted_ids(user_id)
    mutual_ids   = my_conns & their_conns

    if not mutual_ids:
        return []

    return db.query(User).filter(User.id.in_(mutual_ids)).all()
