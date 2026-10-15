"""Normalisation des soumissions Tally (API, webhook, CSV) vers un dictionnaire
« une valeur par variable du codebook ». Les e-mails sont remplacés par un hash salé.
"""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from datetime import datetime
from typing import Any, Iterable

import pandas as pd

TRUE_VALUES = {"true", "1", "oui", "yes", "x", "checked", "vrai"}


def norm_label(s: str | None) -> str:
    """Minuscule, sans accents, sans emoji/ponctuation, espaces normalisés (appariement des libellés)."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def hash_email(email: str | None, salt: str) -> str | None:
    if not email or not str(email).strip():
        return None
    return hashlib.sha256((salt + str(email).strip().lower()).encode("utf-8")).hexdigest()[:24]


class Codebook:
    def __init__(self, cb: dict):
        self.raw = cb
        self.vars: list[dict] = cb["variables"]
        self.by_id = {v["tally_id"]: v for v in self.vars if v.get("tally_id")}
        self.by_name = {v["name"]: v for v in self.vars}
        self.by_label = {norm_label(v["label"]): v for v in self.vars}
        self._labels_sorted = sorted(self.by_label.items(), key=lambda kv: -len(kv[0]))

    def match_label(self, header: str) -> dict | None:
        n = norm_label(header)
        if n in self.by_label:
            return self.by_label[n]
        # tolérance : libellé modifié après coup / tronqué (préfixe d'au moins 40 caractères)
        for lab, v in self._labels_sorted:
            if len(n) >= 40 and (lab.startswith(n[:60]) or n.startswith(lab[:60])):
                return v
        return None

    def match_checkbox_column(self, header: str) -> tuple[dict, str] | None:
        """Colonne CSV de type « Libellé (option) » pour une question à cases à cocher."""
        n = norm_label(header)
        for v in self.vars:
            if v["type"] != "checkbox":
                continue
            ln = norm_label(v["label"])
            if n.startswith(ln[:50]):
                for opt in v.get("options", []):
                    if norm_label(opt) in n[len(ln[:50]):] or norm_label(opt) in n:
                        return v, opt
        return None


def _to_number(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in {"", "-", "."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def coerce(var: dict, value: Any, salt: str) -> Any:
    t = var["type"]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if t == "email":
        v = value[0] if isinstance(value, list) and value else value
        return hash_email(str(v), salt)
    if t == "scale":
        v = value[0] if isinstance(value, list) and value else value
        n = _to_number(v)
        return int(round(n)) if n is not None else None
    if t == "number":
        v = value[0] if isinstance(value, list) and value else value
        return _to_number(v)
    if t == "single":
        if isinstance(value, list):
            return str(value[0]).strip() if value else None
        s = str(value).strip()
        return s or None
    if t in ("multi", "checkbox"):
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        s = str(value).strip()
        if not s:
            return None
        opts = var.get("options") or []
        if opts:
            found = [o for o in opts if norm_label(o) in norm_label(s)]
            if found:
                return found
        return [p.strip() for p in s.split(",") if p.strip()]
    # text
    if isinstance(value, list):
        value = " ".join(str(x) for x in value)
    s = str(value).strip()
    return s or None


def _parse_dt(x: Any) -> datetime | None:
    if not x:
        return None
    try:
        ts = pd.to_datetime(x, utc=True)
        return ts.to_pydatetime()
    except Exception:
        return None


# --- API Tally : GET /forms/{id}/submissions -------------------------------------------------

def normalize_api_payload(payload: dict, cb: Codebook, salt: str) -> list[dict]:
    """Retourne une liste de {id, respondent_id, submitted_at, is_completed, answers, unmapped}."""
    data = payload.get("data", payload)
    questions = {q["id"]: q for q in data.get("questions", [])}
    out = []
    for sub in data.get("submissions", []):
        answers: dict[str, Any] = {}
        unmapped: dict[str, Any] = {}
        for r in sub.get("responses", []):
            qid = r.get("questionId")
            var = cb.by_id.get(qid)
            if var is None and qid in questions:
                var = cb.match_label(questions[qid].get("label", ""))
            if var is None:
                unmapped[qid] = r.get("answer")
                continue
            answers[var["name"]] = coerce(var, r.get("answer"), salt)
        out.append({
            "id": sub["id"],
            "respondent_id": sub.get("respondentId"),
            "submitted_at": _parse_dt(sub.get("submittedAt")),
            "is_completed": bool(sub.get("isCompleted", True)),
            "answers": answers,
            "unmapped": unmapped,
        })
    return out


# --- Webhook Tally : eventType FORM_RESPONSE ---------------------------------------------------

def normalize_webhook(payload: dict, cb: Codebook, salt: str) -> dict:
    d = payload.get("data", {})
    answers: dict[str, Any] = {}
    unmapped: dict[str, Any] = {}
    for f in d.get("fields", []):
        var = cb.by_id.get(f.get("key", "").replace("question_", "")) or cb.match_label(f.get("label", ""))
        value = f.get("value")
        opts = {o.get("id"): o.get("text") for o in (f.get("options") or [])}
        if f.get("type") in {"MULTIPLE_CHOICE", "DROPDOWN", "CHECKBOXES", "MULTI_SELECT", "RANKING"} and isinstance(value, list):
            value = [opts.get(v, v) for v in value]
        elif f.get("type") == "CHECKBOXES" and isinstance(value, bool):
            # champs « une case par option » : la clé porte l'option
            pass
        if var is None:
            unmapped[f.get("key", "?")] = value
            continue
        answers[var["name"]] = coerce(var, value, salt)
    return {
        "id": d.get("submissionId") or d.get("responseId") or payload.get("eventId"),
        "respondent_id": d.get("respondentId"),
        "submitted_at": _parse_dt(d.get("createdAt") or payload.get("createdAt")),
        "is_completed": True,
        "answers": answers,
        "unmapped": unmapped,
    }


# --- Export CSV Tally --------------------------------------------------------------------------

CSV_META = {
    "submission id": "id",
    "respondent id": "respondent_id",
    "submitted at": "submitted_at",
    "id de soumission": "id",
    "id du repondant": "respondent_id",
    "soumis le": "submitted_at",
}


def normalize_csv(content: bytes | str, cb: Codebook, salt: str) -> list[dict]:
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    meta_cols: dict[str, str] = {}
    var_cols: dict[str, dict] = {}
    cb_cols: dict[str, tuple[dict, str]] = {}
    for col in df.columns:
        n = norm_label(col)
        if n in CSV_META:
            meta_cols[col] = CSV_META[n]
            continue
        v = cb.match_label(col)
        if v is not None:
            var_cols[col] = v
            continue
        m = cb.match_checkbox_column(col)
        if m is not None:
            cb_cols[col] = m
    rows = []
    for i, rec in df.iterrows():
        answers: dict[str, Any] = {}
        for col, var in var_cols.items():
            raw = rec[col]
            if raw == "":
                continue
            answers[var["name"]] = coerce(var, raw, salt)
        grouped: dict[str, list[str]] = {}
        for col, (var, opt) in cb_cols.items():
            if str(rec[col]).strip().lower() in TRUE_VALUES:
                grouped.setdefault(var["name"], []).append(opt)
        for k, lst in grouped.items():
            answers.setdefault(k, lst)
        meta = {m: rec[c] for c, m in meta_cols.items()}
        rows.append({
            "id": meta.get("id") or f"csv-{i + 1}",
            "respondent_id": meta.get("respondent_id") or None,
            "submitted_at": _parse_dt(meta.get("submitted_at")),
            "is_completed": True,
            "answers": answers,
            "unmapped": {},
        })
    return rows


def answers_rows_to_frame(rows: Iterable[dict]) -> pd.DataFrame:
    """rows : {id, submitted_at, is_completed, answers, ...} -> DataFrame brute (1 ligne = 1 soumission)."""
    recs = []
    for r in rows:
        rec = {"_id": r["id"], "_respondent": r.get("respondent_id"), "_submitted_at": r.get("submitted_at"),
               "_completed": r.get("is_completed", True)}
        rec.update(r["answers"])
        recs.append(rec)
    return pd.DataFrame(recs)
