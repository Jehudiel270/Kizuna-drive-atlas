"""Chargement des données (base live, instantané figé ou jeu de démonstration), construction du jeu analysable et cache de résultats."""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .core import constructs as C
from .core import plan as P
from .core import synthetic as S
from .core.fmt import jsonable
from .core.labels import short_labels
from .core.normalize import answers_rows_to_frame
from .models import AuditLog, Setting, Snapshot, Submission

_LOCK = threading.RLock()
_DATA_CACHE: dict[tuple, "Source"] = {}
_RESULT_CACHE: dict[tuple, Any] = {}
MAX_CACHE = 24


@dataclass
class Source:
    plan: dict
    codebook: dict
    raw: pd.DataFrame
    df: pd.DataFrame
    key: str
    kind: str  # live | snapshot | demo
    snapshot_id: int | None = None
    labels: dict[str, str] = field(default_factory=dict)
    plan_hash: str = ""
    meta: dict = field(default_factory=dict)


def audit(db: Session, actor: str, action: str, detail: dict | None = None) -> None:
    db.add(AuditLog(actor=actor, action=action, detail=detail or {}))
    db.commit()


def get_setting(db: Session, key: str) -> dict | None:
    row = db.get(Setting, key)
    return row.value if row else None


def set_setting(db: Session, key: str, value: dict) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def del_setting(db: Session, key: str) -> None:
    row = db.get(Setting, key)
    if row is not None:
        db.delete(row)
        db.commit()


def current_plan(db: Session) -> dict:
    return P.get_plan(get_setting(db, "plan_override"))


def current_codebook(db: Session) -> dict:
    return P.get_codebook(get_setting(db, "codebook_override"))


def _live_key(db: Session) -> str:
    n, last = db.execute(select(func.count(Submission.id), func.max(Submission.updated_at))).one()
    nex = db.scalar(select(func.count(Submission.id)).where(Submission.excluded.is_(True))) or 0
    return f"{n}|{last}|{nex}"


def rows_from_db(db: Session, include_excluded: bool = False) -> list[dict]:
    q = select(Submission).order_by(Submission.submitted_at, Submission.id)
    if not include_excluded:
        q = q.where(Submission.excluded.is_(False))
    out = []
    for s in db.scalars(q):
        out.append({"id": s.id, "respondent_id": s.respondent_id, "submitted_at": s.submitted_at, "is_completed": s.is_completed, "answers": s.answers or {}})
    return out


def _frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame({"_id": [], "_respondent": [], "_submitted_at": [], "_completed": []})
    return answers_rows_to_frame(rows)


def _prune() -> None:
    while len(_DATA_CACHE) > MAX_CACHE:
        _DATA_CACHE.pop(next(iter(_DATA_CACHE)))
    while len(_RESULT_CACHE) > MAX_CACHE * 12:
        _RESULT_CACHE.pop(next(iter(_RESULT_CACHE)))


def load_source(db: Session, snapshot_id: int | None = None) -> Source:
    s = get_settings()
    if snapshot_id is not None:
        snap = db.get(Snapshot, snapshot_id)
        if snap is None:
            raise KeyError("snapshot")
        plan = P.get_plan(snap.plan)
        key = f"snap:{snap.id}:{snap.sha256}"
        with _LOCK:
            if key in _DATA_CACHE:
                return _DATA_CACHE[key]
        rows = [dict(r, submitted_at=pd.to_datetime(r.get("submitted_at"), utc=True) if r.get("submitted_at") else None) for r in snap.rows]
        raw = _frame(rows)
        src = Source(plan=plan, codebook=snap.codebook or P.get_codebook(), raw=raw, df=C.build_dataset(raw, plan), key=key, kind="snapshot", snapshot_id=snap.id,
                     plan_hash=snap.plan_hash, meta={"name": snap.name, "created_at": snap.created_at.isoformat(), "sha256": snap.sha256})
        src.labels = short_labels(src.codebook)
        with _LOCK:
            _DATA_CACHE[key] = src
            _prune()
        return src
    plan = current_plan(db)
    codebook = current_codebook(db)
    ph = P.stable_hash(plan)
    if s.demo_mode:
        key = f"demo:{s.demo_n}:{s.demo_seed}:{ph}"
        with _LOCK:
            if key in _DATA_CACHE:
                return _DATA_CACHE[key]
        raw = S.generate(s.demo_n, seed=s.demo_seed)
        kind = "demo"
    else:
        key = f"live:{_live_key(db)}:{ph}:{P.stable_hash(codebook)}"
        with _LOCK:
            if key in _DATA_CACHE:
                return _DATA_CACHE[key]
        raw = _frame(rows_from_db(db))
        kind = "live"
    src = Source(plan=plan, codebook=codebook, raw=raw, df=C.build_dataset(raw, plan), key=key, kind=kind, plan_hash=ph)
    src.labels = short_labels(codebook)
    with _LOCK:
        _DATA_CACHE[key] = src
        _prune()
    return src


def cached(src: Source, name: str, fn: Callable[[], Any], params: Any = None) -> Any:
    k = (src.key, name, json.dumps(params, sort_keys=True, default=str))
    with _LOCK:
        if k in _RESULT_CACHE:
            return _RESULT_CACHE[k]
    val = jsonable(fn())
    with _LOCK:
        _RESULT_CACHE[k] = val
        _prune()
    return val


def clear_caches() -> None:
    with _LOCK:
        _DATA_CACHE.clear()
        _RESULT_CACHE.clear()


def dataset_sha(rows: list[dict]) -> str:
    blob = json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
