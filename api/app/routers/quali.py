"""Analyse de contenu thématique des réponses ouvertes (protocole 5.4) : codebook de thèmes, codage, synthèse échec/succès, accord inter-codeurs."""
from __future__ import annotations

import itertools
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from scipy import stats
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CodedSegment, Theme, User
from ..security import current_user, require_role
from ..service import Source, audit
from ..stats import textmining as T
from .deps import get_source

router = APIRouter(prefix="/quali", tags=["qualitatif"])

QUESTIONS = {"txt_facteur": "Facteur principal du résultat", "txt_autre": "Autre commentaire"}


class ThemeIn(BaseModel):
    name: str
    description: str = ""
    color: str = "#6ea8ff"
    parent_dimension: str = ""


class CodeIn(BaseModel):
    submission_id: str
    question: str
    theme_id: int


def _theme_dict(t: Theme) -> dict:
    return {"id": t.id, "name": t.name, "description": t.description, "color": t.color, "parent_dimension": t.parent_dimension}


@router.get("/themes")
def themes(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [_theme_dict(t) for t in db.scalars(select(Theme).order_by(Theme.id))]


@router.post("/themes")
def create_theme(body: ThemeIn, db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Nom obligatoire")
    if db.scalar(select(Theme).where(Theme.name == name)):
        raise HTTPException(409, "Thème déjà existant")
    t = Theme(name=name, description=body.description, color=body.color, parent_dimension=body.parent_dimension)
    db.add(t)
    db.commit()
    return _theme_dict(t)


@router.put("/themes/{tid}")
def update_theme(tid: int, body: ThemeIn, db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    t = db.get(Theme, tid)
    if t is None:
        raise HTTPException(404, "Thème introuvable")
    t.name, t.description, t.color, t.parent_dimension = body.name.strip(), body.description, body.color, body.parent_dimension
    db.commit()
    return _theme_dict(t)


@router.delete("/themes/{tid}")
def delete_theme(tid: int, db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    t = db.get(Theme, tid)
    if t is None:
        raise HTTPException(404, "Thème introuvable")
    db.delete(t)
    db.commit()
    audit(db, user.email, "theme.delete", {"id": tid, "name": t.name})
    return {"ok": True}


@router.get("/answers")
def answers(src: Source = Depends(get_source), db: Session = Depends(get_db), user: User = Depends(current_user)):
    docs = T.open_answers(src.df)
    segs = db.scalars(select(CodedSegment)).all()
    codes: dict[tuple, list] = defaultdict(list)
    for s in segs:
        codes[(s.submission_id, s.question)].append({"theme_id": s.theme_id, "coder": s.coder})
    return {"items": [{**d, "question_label": QUESTIONS.get(d["question"], d["question"]), "codes": codes.get((d["submission_id"], d["question"]), [])} for d in docs],
            "me": user.email}


@router.post("/code")
def code(body: CodeIn, db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    if body.question not in QUESTIONS:
        raise HTTPException(400, "Question inconnue")
    if db.get(Theme, body.theme_id) is None:
        raise HTTPException(404, "Thème introuvable")
    ex = db.scalar(select(CodedSegment).where(CodedSegment.submission_id == body.submission_id, CodedSegment.question == body.question,
                                              CodedSegment.theme_id == body.theme_id, CodedSegment.coder == user.email))
    if ex is None:
        db.add(CodedSegment(submission_id=body.submission_id, question=body.question, theme_id=body.theme_id, coder=user.email))
        db.commit()
    return {"ok": True}


@router.delete("/code")
def uncode(submission_id: str, question: str, theme_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("analyste"))):
    ex = db.scalar(select(CodedSegment).where(CodedSegment.submission_id == submission_id, CodedSegment.question == question,
                                              CodedSegment.theme_id == theme_id, CodedSegment.coder == user.email))
    if ex is not None:
        db.delete(ex)
        db.commit()
    return {"ok": True}


@router.get("/synthesis")
def synthesis(coder: str | None = None, src: Source = Depends(get_source), db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Fréquence de chaque thème parmi les projets en échec vs en succès (test exact de Fisher). Unité = projet (soumission)."""
    issue = src.df[src.df["analysable"]].set_index("_id")["issue"].to_dict()
    n_e = sum(1 for v in issue.values() if v in ("echec_partiel", "echec_total"))
    n_s = sum(1 for v in issue.values() if v == "succes")
    segs = db.scalars(select(CodedSegment)).all()
    ths = {t.id: t for t in db.scalars(select(Theme))}
    per: dict[int, set] = defaultdict(set)
    coded_units = set()
    for s in segs:
        if coder and s.coder != coder:
            continue
        if s.submission_id in issue:
            per[s.theme_id].add(s.submission_id)
            coded_units.add(s.submission_id)
    out = []
    for tid, subs in per.items():
        a = sum(1 for sid in subs if issue[sid] in ("echec_partiel", "echec_total"))
        b = sum(1 for sid in subs if issue[sid] == "succes")
        p = None
        orr = None
        if n_e and n_s:
            table = [[a, n_e - a], [b, n_s - b]]
            orr, p = stats.fisher_exact(table)
            orr = None if orr != orr or orr in (float("inf"),) else float(orr)
        out.append({"theme": _theme_dict(ths[tid]) if tid in ths else {"id": tid, "name": "?"}, "n_echec": a, "n_succes": b,
                    "pct_echec": a / n_e if n_e else None, "pct_succes": b / n_s if n_s else None, "odds_ratio": orr, "p_fisher": float(p) if p is not None else None})
    out.sort(key=lambda r: -(r["n_echec"] + r["n_succes"]))
    return {"n_echec": n_e, "n_succes": n_s, "n_coded_projects": len(coded_units), "themes": out,
            "note": "Descriptif exploratoire : p de Fisher non corrigés, à ne pas lire comme des tests confirmatoires (le protocole n'en prévoit pas)."}


def cohen_kappa(a: list[int], b: list[int]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if pe == 1:
        return None
    return float((po - pe) / (1 - pe))


@router.get("/kappa")
def kappa(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Accord inter-codeurs (kappa de Cohen) pour chaque paire de codeurs, sur les unités (projet × question) codées par au moins l'un des deux."""
    segs = db.scalars(select(CodedSegment)).all()
    ths = [t.id for t in db.scalars(select(Theme))]
    by_coder: dict[str, dict[tuple, set]] = defaultdict(lambda: defaultdict(set))
    for s in segs:
        by_coder[s.coder][(s.submission_id, s.question)].add(s.theme_id)
    out = []
    for c1, c2 in itertools.combinations(sorted(by_coder), 2):
        units = sorted(set(by_coder[c1]) | set(by_coder[c2]))
        va, vb = [], []
        per_theme = []
        for tid in ths:
            a = [int(tid in by_coder[c1].get(u, set())) for u in units]
            b = [int(tid in by_coder[c2].get(u, set())) for u in units]
            va += a
            vb += b
            per_theme.append({"theme_id": tid, "kappa": cohen_kappa(a, b)})
        k = cohen_kappa(va, vb)
        label = None if k is None else ("presque parfait" if k >= 0.81 else "substantiel" if k >= 0.61 else "modéré" if k >= 0.41 else "faible")
        out.append({"coder_a": c1, "coder_b": c2, "n_units": len(units), "kappa": k, "interpretation": label, "per_theme": per_theme})
    return {"pairs": out, "coders": sorted(by_coder), "note": "Seuil usuel : κ ≥ 0,61 (accord substantiel, Landis & Koch)."}
