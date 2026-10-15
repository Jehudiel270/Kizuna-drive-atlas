"""Authentification JWT, hachage bcrypt, rôles (admin > analyste > lecteur)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User

ROLE_RANK = {"lecteur": 1, "analyste": 2, "admin": 3}
bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(user: User) -> str:
    s = get_settings()
    payload = {"sub": str(user.id), "email": user.email, "role": user.role, "exp": datetime.now(timezone.utc) + timedelta(hours=s.token_ttl_hours)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def bootstrap_admin(db: Session) -> None:
    """Crée (ou met à jour) l'administrateur initial à partir de ADMIN_EMAIL / ADMIN_PASSWORD."""
    s = get_settings()
    if not s.admin_email or not s.admin_password:
        return
    u = db.scalar(select(User).where(User.email == s.admin_email))
    if u is None:
        db.add(User(email=s.admin_email, name="Administrateur", password_hash=hash_password(s.admin_password), role="admin"))
        db.commit()


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    s = get_settings()
    if s.demo_mode:
        return User(id=0, email="demo@kizuna.local", name="Démo", password_hash="", role="admin")
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise")
    try:
        payload = jwt.decode(creds.credentials, s.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide ou expiré")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur inconnu")
    return user


def require_role(minimum: str):
    def dep(user: User = Depends(current_user)) -> User:
        if ROLE_RANK.get(user.role, 0) < ROLE_RANK[minimum]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Rôle « {minimum} » requis")
        return user
    return dep
