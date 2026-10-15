"""Plan d'analyse pré-enregistré et codebook : lecture, modification contrôlée (admin), historique d'empreintes."""
from __future__ import annotations

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import plan as P
from ..db import get_db
from ..models import AuditLog, User
from ..security import current_user, require_role
from ..service import audit, clear_caches, current_codebook, current_plan, del_setting, get_setting, set_setting
from .deps import forbid_in_demo

router = APIRouter(prefix="/config", tags=["configuration"])


class TextIn(BaseModel):
    text: str
    note: str = ""


@router.get("/plan")
def get_plan(db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = current_plan(db)
    ov = get_setting(db, "plan_override")
    return {"plan": plan, "hash": P.stable_hash(plan), "customized": bool(ov), "default_text": P.default_plan_text(),
            "override_text": yaml.safe_dump(ov, allow_unicode=True, sort_keys=False) if ov else ""}


@router.put("/plan")
def put_plan(body: TextIn, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    """Enregistre des surcharges du plan (YAML ou JSON, fusion profonde avec le plan par défaut). Chaque modification est journalisée."""
    forbid_in_demo()
    try:
        ov = yaml.safe_load(body.text) or {}
    except yaml.YAMLError as e:
        raise HTTPException(400, f"YAML invalide : {e}")
    if not isinstance(ov, dict):
        raise HTTPException(400, "Le plan doit être un objet (clés/valeurs)")
    errs = P.validate_plan(P.get_plan(ov))
    if errs:
        raise HTTPException(422, {"errors": errs})
    before = P.stable_hash(current_plan(db))
    set_setting(db, "plan_override", ov)
    clear_caches()
    after = P.stable_hash(current_plan(db))
    audit(db, admin.email, "plan.update", {"hash_before": before, "hash_after": after, "note": body.note})
    return {"hash": after}


@router.post("/plan/reset")
def reset_plan(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    forbid_in_demo()
    del_setting(db, "plan_override")
    clear_caches()
    audit(db, admin.email, "plan.reset", {})
    return {"hash": P.stable_hash(current_plan(db))}


@router.get("/codebook")
def get_codebook(db: Session = Depends(get_db), user: User = Depends(current_user)):
    cb = current_codebook(db)
    return {"codebook": cb, "customized": bool(get_setting(db, "codebook_override")), "default_text": P.default_codebook_text()}


@router.put("/codebook")
def put_codebook(body: TextIn, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    forbid_in_demo()
    try:
        cb = yaml.safe_load(body.text)
    except yaml.YAMLError as e:
        raise HTTPException(400, f"YAML invalide : {e}")
    if not isinstance(cb, dict) or not isinstance(cb.get("variables"), list):
        raise HTTPException(422, "Le codebook doit contenir une liste « variables »")
    names = [v.get("name") for v in cb["variables"]]
    if len(names) != len(set(names)) or any(not n for n in names):
        raise HTTPException(422, "Noms de variables manquants ou dupliqués")
    set_setting(db, "codebook_override", cb)
    clear_caches()
    audit(db, admin.email, "codebook.update", {"n_variables": len(names), "note": body.note})
    return {"n_variables": len(names)}


@router.post("/codebook/reset")
def reset_codebook(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    forbid_in_demo()
    del_setting(db, "codebook_override")
    clear_caches()
    audit(db, admin.email, "codebook.reset", {})
    return {"ok": True}


@router.get("/audit")
def audit_log(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))).all()
    return [{"at": r.at.isoformat(), "actor": r.actor, "action": r.action, "detail": r.detail} for r in rows]
