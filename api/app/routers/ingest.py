"""Réception des données Tally : webhook signé, synchronisation par l'API Tally, import CSV ; exclusions manuelles."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..core import constructs as C
from ..core.normalize import Codebook, normalize_api_payload, normalize_csv, normalize_webhook
from ..db import get_db
from ..models import Submission, User
from ..security import current_user, require_role
from ..service import audit, clear_caches, current_codebook, current_plan, get_setting, load_source, set_setting
from .deps import forbid_in_demo

router = APIRouter(prefix="/ingest", tags=["ingestion"])


def upsert_rows(db: Session, rows: list[dict], source: str, form_id: str) -> dict:
    ins = upd = 0
    for r in rows:
        if not r.get("id"):
            continue
        cur = db.get(Submission, r["id"])
        if cur is None:
            db.add(Submission(id=r["id"], respondent_id=r.get("respondent_id"), form_id=form_id, submitted_at=r.get("submitted_at"),
                              is_completed=r.get("is_completed", True), source=source, answers=r["answers"], unmapped=r.get("unmapped", {})))
            ins += 1
        else:
            cur.answers = r["answers"]
            cur.unmapped = r.get("unmapped", {})
            cur.is_completed = r.get("is_completed", True)
            cur.respondent_id = r.get("respondent_id") or cur.respondent_id
            cur.submitted_at = r.get("submitted_at") or cur.submitted_at
            cur.source = source
            upd += 1
    db.commit()
    clear_caches()
    return {"inserted": ins, "updated": upd, "received": len(rows)}


def verify_signature(secret: str, raw: bytes, header: str | None) -> bool:
    if not header or not secret:
        return False
    expected = base64.b64encode(hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()).decode("ascii")
    return hmac.compare_digest(expected, header.strip())


@router.post("/webhook/tally")
async def tally_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook Tally (événement FORM_RESPONSE). Signature : en-tête `Tally-Signature` = base64(HMAC-SHA256(corps, secret))."""
    s = get_settings()
    raw = await request.body()
    if not s.tally_signing_secret:
        raise HTTPException(503, "Webhook non configuré : définir TALLY_SIGNING_SECRET")
    if not verify_signature(s.tally_signing_secret, raw, request.headers.get("tally-signature")):
        raise HTTPException(401, "Signature invalide")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("eventType") not in (None, "FORM_RESPONSE"):
        return {"ignored": payload.get("eventType")}
    form_id = (payload.get("data") or {}).get("formId", s.tally_form_id)
    if s.tally_form_id and form_id and form_id != s.tally_form_id:
        raise HTTPException(400, "Formulaire inattendu")
    row = normalize_webhook(payload, Codebook(current_codebook(db)), s.email_salt)
    res = upsert_rows(db, [row], "webhook", form_id)
    set_setting(db, "last_webhook", {"at": datetime.now(timezone.utc).isoformat(), "id": row["id"]})
    return res


@router.post("/sync")
def sync_from_tally(db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    """Tire toutes les soumissions via l'API Tally (pagination) ; idempotent."""
    forbid_in_demo()
    s = get_settings()
    if not s.tally_api_key:
        raise HTTPException(503, "TALLY_API_KEY non configurée")
    cb = Codebook(current_codebook(db))
    headers = {"Authorization": f"Bearer {s.tally_api_key}"}
    total = {"inserted": 0, "updated": 0, "received": 0, "pages": 0}
    page = 1
    with httpx.Client(base_url=s.tally_base, headers=headers, timeout=30) as client:
        while True:
            r = client.get(f"/forms/{s.tally_form_id}/submissions", params={"page": page, "filter": "all"})
            if r.status_code == 401:
                raise HTTPException(502, "Clé API Tally refusée")
            if r.status_code >= 400:
                raise HTTPException(502, f"Erreur API Tally ({r.status_code})")
            payload = r.json()
            rows = normalize_api_payload(payload, cb, s.email_salt)
            res = upsert_rows(db, rows, "api", s.tally_form_id)
            for k in ("inserted", "updated", "received"):
                total[k] += res[k]
            total["pages"] += 1
            if not payload.get("hasMore") or page >= 200:
                break
            page += 1
    set_setting(db, "last_sync", {"at": datetime.now(timezone.utc).isoformat(), **total})
    audit(db, user.email, "ingest.sync", total)
    return total


@router.post("/csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    forbid_in_demo()
    content = await file.read()
    if len(content) > 15_000_000:
        raise HTTPException(413, "Fichier trop volumineux (15 Mo max)")
    s = get_settings()
    rows = normalize_csv(content, Codebook(current_codebook(db)), s.email_salt)
    if not rows:
        raise HTTPException(400, "Aucune ligne reconnue dans le CSV")
    mapped = sum(1 for r in rows if r["answers"])
    res = upsert_rows(db, rows, "csv", s.tally_form_id)
    res["rows_with_data"] = mapped
    audit(db, user.email, "ingest.csv", {"file": file.filename, **res})
    return res


@router.get("/status")
def status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = get_settings()
    n = db.scalar(select(func.count(Submission.id))) or 0
    nex = db.scalar(select(func.count(Submission.id)).where(Submission.excluded.is_(True))) or 0
    by_src = dict(db.execute(select(Submission.source, func.count(Submission.id)).group_by(Submission.source)).all())
    src = load_source(db)
    return {
        "demo": s.demo_mode, "form_id": s.tally_form_id, "form_url": f"https://tally.so/r/{s.tally_form_id}",
        "n_submissions": n, "n_excluded": nex, "by_source": by_src,
        "api_key_configured": bool(s.tally_api_key), "webhook_secret_configured": bool(s.tally_signing_secret),
        "last_sync": get_setting(db, "last_sync"), "last_webhook": get_setting(db, "last_webhook"),
        "n_analysable": int(src.df["analysable"].sum()) if len(src.df) else 0, "source_kind": src.kind,
    }


@router.get("/submissions")
def list_submissions(page: int = 1, size: int = 50, db: Session = Depends(get_db), user: User = Depends(current_user)):
    size = min(max(size, 1), 200)
    total = db.scalar(select(func.count(Submission.id))) or 0
    rows = db.scalars(select(Submission).order_by(Submission.submitted_at.desc().nullslast(), Submission.id).offset((page - 1) * size).limit(size)).all()
    src = load_source(db)
    meta = src.df.set_index("_id")[["consent_ok", "declared_ok", "project_ok", "issue", "analysable"]].to_dict("index") if len(src.df) else {}
    out = []
    for r in rows:
        m = meta.get(r.id, {})
        out.append({"id": r.id, "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None, "source": r.source, "is_completed": r.is_completed,
                    "excluded": r.excluded, "exclusion_reason": r.exclusion_reason, "issue": m.get("issue") if isinstance(m.get("issue"), str) else None,
                    "analysable": bool(m.get("analysable", False)), "enqueteur": (r.answers or {}).get("enqueteur"), "relais": (r.answers or {}).get("relais"),
                    "n_answers": len(r.answers or {})})
    return {"total": total, "page": page, "size": size, "items": out}


class ExcludeIn(BaseModel):
    excluded: bool
    reason: str | None = None


@router.patch("/submissions/{sid}")
def exclude(sid: str, body: ExcludeIn, db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    forbid_in_demo()
    r = db.get(Submission, sid)
    if r is None:
        raise HTTPException(404, "Soumission introuvable")
    if body.excluded and not (body.reason or "").strip():
        raise HTTPException(400, "Un motif d'exclusion est obligatoire (traçabilité)")
    r.excluded, r.exclusion_reason = body.excluded, (body.reason or None) if body.excluded else None
    db.commit()
    clear_caches()
    audit(db, user.email, "submission.exclude" if body.excluded else "submission.include", {"id": sid, "reason": body.reason})
    return {"ok": True}


class PurgeIn(BaseModel):
    confirm: str


@router.post("/purge")
def purge(body: PurgeIn, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    """Supprime toutes les soumissions (ex. réponses de test avant le lancement de la collecte)."""
    forbid_in_demo()
    if body.confirm != "SUPPRIMER":
        raise HTTPException(400, "Confirmation incorrecte : saisir SUPPRIMER")
    n = db.execute(delete(Submission)).rowcount
    db.commit()
    clear_caches()
    audit(db, user.email, "ingest.purge", {"deleted": n})
    return {"deleted": n}
