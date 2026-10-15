"""Suivi de collecte : entonnoir d'éligibilité, avancement vs cible, quotas, relais, enquêteurs, qualité."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from ..core.constructs import OUTCOME_ORDER
from . import hypotheses as H

LIKERT_ITEMS = [
    "gov_unique", "gov_consult", "gov_discute", "gov_impose", "gov_liens", "comp_dirigeants", "comp_utilisateurs", "com_info", "com_points",
    "com_alerte", "dir_suivi", "dir_moyens", "dir_blocages", "dir_priorite", "env_adequation", "env_simplicite", "env_coupures", "env_pression", "form_ecrit",
]


def hhi(counts: pd.Series) -> float:
    tot = counts.sum()
    if tot == 0:
        return float("nan")
    sh = counts / tot
    return float((sh ** 2).sum())


def _dist(s: pd.Series, targets: dict | None = None) -> list[dict]:
    vc = s.dropna().value_counts()
    tot = int(vc.sum())
    rows = []
    keys = list(dict.fromkeys(list(vc.index) + list((targets or {}).keys())))
    for k in keys:
        n = int(vc.get(k, 0))
        tgt = (targets or {}).get(k)
        rows.append({"value": str(k), "n": n, "pct": n / tot if tot else 0.0, "target": tgt, "gap": (tgt - n) if tgt is not None else None})
    return sorted(rows, key=lambda r: -r["n"])


def collecte_summary(df: pd.DataFrame, plan: dict) -> dict:
    g = plan["general"]
    tgt = g["target_n"]
    total = int(len(df))
    consent = int(df["consent_ok"].sum())
    declared = int((df["consent_ok"] & df["declared_ok"]).sum())
    project = int((df["consent_ok"] & df["declared_ok"] & df["project_ok"]).sum())
    classable = int(df["analysable"].sum())
    ongoing = int(((df["consent_ok"] & df["declared_ok"] & df["project_ok"]) & (df["issue"] == "en_cours")).sum())
    est = H.build_frame(df, plan, H.SPECS[0])
    complete_model = int(len(est[0]))
    base = df[df["analysable"]]
    funnel = [
        {"step": "Soumissions reçues", "n": total},
        {"step": "Consentement donné", "n": consent},
        {"step": "Entreprise déclarée", "n": declared},
        {"step": "Projet numérique depuis 2024", "n": project},
        {"step": "Issue classable (hors « en cours »)", "n": classable},
        {"step": "Complet pour les modèles (H1–H5)", "n": complete_model},
    ]
    # relais / enquêteurs
    rel_counts = base["relais"].fillna("(non renseigné)").value_counts() if "relais" in base else pd.Series(dtype=int)
    top_share = float(rel_counts.iloc[0] / rel_counts.sum()) if len(rel_counts) else None
    # séries temporelles
    ts = None
    if "_submitted_at" in df and df["_submitted_at"].notna().any():
        d = df.copy()
        d["day"] = pd.to_datetime(d["_submitted_at"], utc=True).dt.strftime("%Y-%m-%d")
        daily = d.groupby("day").agg(total=("day", "size"), analysable=("analysable", "sum")).sort_index()
        ts = [{"day": k, "total": int(r.total), "analysable": int(r.analysable), "cum_total": int(daily["total"].cumsum()[k]),
               "cum_analysable": int(daily["analysable"].cumsum()[k])} for k, r in daily.iterrows()]
    # alertes qualité
    lik = df[[c for c in LIKERT_ITEMS if c in df]].apply(pd.to_numeric, errors="coerce")
    straight = int(((lik.notna().sum(axis=1) >= 10) & (lik.nunique(axis=1) == 1) & df["analysable"]).sum())
    incoh = int(df.loc[df["analysable"], "issue_flags"].map(lambda x: len(x) > 0).sum()) if "issue_flags" in df else 0
    dup_resp = 0
    if "_respondent" in df and df["_respondent"].notna().any():
        dup_resp = int(df["_respondent"].dropna().duplicated().sum())
    dup_email = int(df["email"].dropna().duplicated().sum()) if "email" in df else 0
    mi = pd.to_numeric(df.get("comp_habitues"), errors="coerce") > pd.to_numeric(df.get("comp_nb_employes"), errors="coerce")
    incoh_hab = int((mi & df["analysable"]).sum())
    alerts = []
    if classable < tgt["min"]:
        alerts.append({"level": "info", "text": f"{classable} projets analysables sur une cible de {tgt['min']}–{tgt['max']} ({classable / tgt['min']:.0%} du minimum)."})
    if top_share is not None and top_share > 0.30 and rel_counts.sum() >= 20:
        alerts.append({"level": "warn", "text": f"Le relais « {rel_counts.index[0]} » concentre {top_share:.0%} des réponses : biais de recrutement possible."})
    if straight:
        alerts.append({"level": "warn", "text": f"{straight} réponse(s) avec la même note à toutes les échelles (réponse bâclée possible)."})
    if dup_resp or dup_email:
        alerts.append({"level": "warn", "text": f"Doublons probables : {dup_resp} identifiant(s) de répondant et {dup_email} e-mail(s) répétés (un seul répondant par projet, protocole 4.5)."})
    if incoh:
        alerts.append({"level": "warn", "text": f"{incoh} réponse(s) avec une issue incohérente (ex. « arrêté » mais « utilisé régulièrement »)."})
    if incoh_hab:
        alerts.append({"level": "warn", "text": f"{incoh_hab} réponse(s) où le nombre d'employés habitués au numérique dépasse le nombre d'employés du projet."})
    if ongoing:
        alerts.append({"level": "info", "text": f"{ongoing} projet(s) « en cours » : non classables, exclus des modèles (à documenter dans le rapport)."})
    q = plan.get("quotas", {})
    return {
        "target": tgt,
        "n_total": total,
        "n_analysable": classable,
        "n_model": complete_model,
        "progress_min": classable / tgt["min"] if tgt["min"] else None,
        "progress_max": classable / tgt["max"] if tgt["max"] else None,
        "funnel": funnel,
        "issue": _dist(base["issue"].map(lambda v: {"succes": "Succès", "echec_partiel": "Échec partiel", "echec_total": "Échec total"}.get(v, v))),
        "secteur": _dist(base["secteur_g"], q.get("secteur_g")),
        "taille": _dist(base["taille_g"], q.get("taille_g")),
        "ville": _dist(base["ville"], q.get("ville")),
        "mode": _dist(base["mode"]),
        "relais": _dist(base["relais"].fillna("(non renseigné)")) if "relais" in base else [],
        "relais_hhi": hhi(rel_counts) if len(rel_counts) else None,
        "relais_top_share": top_share,
        "enqueteurs": _dist(base["enqueteur"]) if "enqueteur" in base else [],
        "quota_cross": _cross(base, "secteur_g", "taille_g"),
        "timeline": ts,
        "quality": {"straightlining": straight, "duplicates_respondent": dup_resp, "duplicates_email": dup_email, "incoherent_outcome": incoh,
                    "habitues_gt_employes": incoh_hab},
        "alerts": alerts,
    }


def _cross(base: pd.DataFrame, a: str, b: str) -> dict:
    t = pd.crosstab(base[a], base[b])
    order = ["<10", "10-49", "50+"]
    t = t[sorted(t.columns, key=lambda c: (order.index(c) if c in order else 99, str(c)))]
    return {"rows": [str(x) for x in t.index], "cols": [str(x) for x in t.columns], "values": t.values.astype(int).tolist()}
