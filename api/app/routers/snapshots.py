"""Instantanés figés : jeu de données + plan + empreinte SHA-256, pour que les chiffres du rapport restent reproductibles."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import plan as P
from ..db import get_db
from ..models import Snapshot, User
from ..security import current_user, require_role
from ..service import audit, current_codebook, current_plan, dataset_sha, rows_from_db
from .deps import forbid_in_demo

router = APIRouter(prefix="/snapshots", tags=["instantanés"])


class SnapIn(BaseModel):
    name: str
    note: str = ""


def _d(s: Snapshot) -> dict:
    return {"id": s.id, "name": s.name, "note": s.note, "created_at": s.created_at.isoformat(), "created_by": s.created_by, "n_rows": s.n_rows,
            "sha256": s.sha256, "plan_hash": s.plan_hash}


@router.get("")
def list_snapshots(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [_d(s) for s in db.scalars(select(Snapshot).order_by(Snapshot.id.desc()))]


@router.post("")
def create_snapshot(body: SnapIn, db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    forbid_in_demo()
    if not body.name.strip():
        raise HTTPException(400, "Nom obligatoire")
    rows = rows_from_db(db)
    if not rows:
        raise HTTPException(409, "Aucune donnée à figer")
    ser = [{"id": r["id"], "respondent_id": r["respondent_id"], "submitted_at": r["submitted_at"].isoformat() if r["submitted_at"] else None,
            "is_completed": r["is_completed"], "answers": r["answers"]} for r in rows]
    plan = current_plan(db)
    s = Snapshot(name=body.name.strip(), note=body.note, created_by=user.email, n_rows=len(ser), sha256=dataset_sha(ser), plan_hash=P.stable_hash(plan),
                 plan=plan, codebook=current_codebook(db), rows=ser)
    db.add(s)
    db.commit()
    audit(db, user.email, "snapshot.create", {"id": s.id, "sha256": s.sha256, "n": s.n_rows})
    return _d(s)


@router.delete("/{sid}")
def delete_snapshot(sid: int, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    s = db.get(Snapshot, sid)
    if s is None:
        raise HTTPException(404, "Introuvable")
    db.delete(s)
    db.commit()
    audit(db, user.email, "snapshot.delete", {"id": sid})
    return {"ok": True}
