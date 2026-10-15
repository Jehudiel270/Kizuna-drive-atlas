from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import User
from ..security import create_token, current_user, hash_password, require_role, verify_password
from ..service import audit

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class UserIn(BaseModel):
    email: str
    name: str = ""
    password: str
    role: str = "analyste"


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if u is None or not u.active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Identifiants incorrects")
    return {"token": create_token(u), "user": {"email": u.email, "name": u.name, "role": u.role}}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email, "name": user.name, "role": user.role, "demo": get_settings().demo_mode}


@router.get("/users")
def users(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role, "active": u.active} for u in db.scalars(select(User).order_by(User.id))]


@router.post("/users")
def create_user(body: UserIn, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    if body.role not in ("admin", "analyste", "lecteur"):
        raise HTTPException(400, "Rôle invalide")
    if len(body.password) < 10:
        raise HTTPException(400, "Mot de passe : 10 caractères minimum")
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "E-mail déjà utilisé")
    u = User(email=email, name=body.name, password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    db.commit()
    audit(db, admin.email, "user.create", {"email": email, "role": body.role})
    return {"id": u.id, "email": u.email, "role": u.role}


@router.delete("/users/{uid}")
def deactivate(uid: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    u = db.get(User, uid)
    if u is None:
        raise HTTPException(404, "Introuvable")
    if u.email == admin.email:
        raise HTTPException(400, "Impossible de désactiver son propre compte")
    u.active = False
    db.commit()
    audit(db, admin.email, "user.deactivate", {"email": u.email})
    return {"ok": True}
