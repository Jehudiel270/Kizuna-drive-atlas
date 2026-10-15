"""Construction des variables d'analyse à partir des réponses normalisées.

Tout est piloté par le plan (plan.yaml) : règles de l'issue, items des échelles, formalisation, regroupements.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

OUTCOME_ORDER = ["succes", "echec_partiel", "echec_total"]
OUTCOME_LABELS = {
    "succes": "Succès",
    "echec_partiel": "Échec partiel",
    "echec_total": "Échec total",
    "en_cours": "En cours (non classable)",
}


def _starts(val: Any, prefix: str) -> bool:
    return isinstance(val, str) and val.strip().lower().startswith(prefix.strip().lower())


def _yes(val: Any) -> bool | None:
    if not isinstance(val, str):
        return None
    v = val.strip().lower()
    if v.startswith("oui"):
        return True
    if v.startswith("non"):
        return False
    return None


def rate_class(val: Any) -> float:
    """« 0 à 24 % » -> 1 ; « 25 à 49 % » -> 2 ; « 50 à 74 % » -> 3 ; « 75 à 100 % » -> 4."""
    if not isinstance(val, str):
        return np.nan
    v = val.strip()
    if v.startswith("0"):
        return 1
    if v.startswith("25"):
        return 2
    if v.startswith("50"):
        return 3
    if v.startswith("75"):
        return 4
    return np.nan


def classify_outcome(row: pd.Series, plan: dict) -> tuple[str | float, list[str]]:
    o = plan["outcome"]
    flags: list[str] = []
    usage = row.get("usage_actuel")
    arrete = _yes(row.get("arrete"))
    retour = _yes(row.get("retour_ancien"))
    cls = rate_class(row.get("usage_taux"))
    if not isinstance(usage, str):
        return np.nan, ["issue_manquante"]
    if _starts(usage, o["usage_ongoing_startswith"]):
        if arrete:
            flags.append("incoherence: en cours mais arrêté")
        return "en_cours", flags
    total = _starts(usage, o["usage_total_startswith"]) or (o.get("stopped_is_total", True) and arrete is True)
    if total:
        if _starts(usage, o["usage_success_startswith"]):
            flags.append("incoherence: usage régulier mais arrêté")
        return "echec_total", flags
    partial = (
        _starts(usage, o["usage_partial_startswith"])
        or (o.get("reverted_is_partial", True) and retour is True)
        or (not math.isnan(cls) and cls <= o.get("partial_max_rate_class", 2))
    )
    if _starts(usage, o["usage_success_startswith"]) and not partial:
        return "succes", flags
    if _starts(usage, o["usage_success_startswith"]) and partial:
        if not math.isnan(cls) and cls <= o.get("partial_max_rate_class", 2):
            flags.append("incoherence: usage régulier mais < 50 % d'utilisateurs")
        if retour is True:
            flags.append("retour aux anciennes méthodes malgré usage régulier")
    return "echec_partiel", flags


def _scale_score(df: pd.DataFrame, items: list[str], reverse: list[str], lo: int, hi: int, min_frac: float) -> pd.Series:
    cols = []
    for it in items:
        s = pd.to_numeric(df.get(it), errors="coerce") if it in df else pd.Series(np.nan, index=df.index)
        if it in reverse:
            s = (lo + hi) - s
        cols.append(s)
    m = pd.concat(cols, axis=1)
    n_ok = m.notna().sum(axis=1)
    score = m.mean(axis=1)
    score[n_ok < max(1, math.ceil(min_frac * len(items)))] = np.nan
    return score


def _map_group(series: pd.Series, mapping: dict[str, str]) -> pd.Series:
    def f(v):
        if not isinstance(v, str):
            return np.nan
        if v in mapping:
            return mapping[v]
        for k, g in mapping.items():
            if v.startswith(k):
                return g
        return np.nan
    return series.map(f)


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=1)
    if not sd or np.isnan(sd):
        return s * np.nan
    return (s - s.mean()) / sd


def formalisation_index(df: pd.DataFrame, plan: dict) -> pd.Series:
    fp = plan["formalisation"]
    w = fp["weights"]
    lo, hi = plan["general"]["likert"]["min"], plan["general"]["likert"]["max"]
    ecrit = (pd.to_numeric(df.get("form_ecrit"), errors="coerce") - lo) / (hi - lo)

    def yes_share(row):
        vals = [_yes(row.get(c)) for c in ("form_compta", "form_contrats", "form_organigramme")]
        known = [v for v in vals if v is not None]
        if len(known) < 2:
            return np.nan
        return sum(known) / len(known)

    docs = df.apply(yes_share, axis=1)
    counted = [p.lower() for p in fp["papers_counted"]]

    def papers(v):
        if not isinstance(v, list):
            return np.nan
        if len(v) > 0 and all(str(x).lower().startswith("je ne sais pas") for x in v):
            return np.nan
        n = sum(any(str(x).lower().startswith(c) for c in counted) for x in v)
        return min(n, len(counted)) / len(counted)

    pap = df["form_papiers"].map(papers) if "form_papiers" in df else pd.Series(np.nan, index=df.index)
    comp = pd.concat([ecrit, docs, pap], axis=1)
    comp.columns = ["ecrit", "documents", "papiers"]
    weights = np.array([w["ecrit"], w["documents"], w["papiers"]], dtype=float)
    vals = comp.to_numpy(dtype=float)
    mask = ~np.isnan(vals)
    num = np.nansum(vals * weights, axis=1)
    den = (mask * weights).sum(axis=1)
    idx = np.where(mask.sum(axis=1) >= 2, num / np.where(den == 0, np.nan, den), np.nan)
    return pd.Series(idx, index=df.index)


def formalisation_category(idx: pd.Series, plan: dict) -> pd.Series:
    th = plan["formalisation"]["thresholds"]

    def f(v):
        if pd.isna(v):
            return np.nan
        if v < th["informel_lt"]:
            return "informel"
        if v >= th["formel_ge"]:
            return "formel"
        return "semi-formel"

    return idx.map(f)


def famille_flag(df: pd.DataFrame) -> pd.Series:
    def f(row):
        a, b = _yes(row.get("famille_propriete")), _yes(row.get("famille_postes"))
        if a is True or b is True:
            return 1.0
        if a is False and b is False:
            return 0.0
        return np.nan

    return df.apply(f, axis=1)


def type_projet(v: Any) -> Any:
    if not isinstance(v, list) or not v:
        return np.nan
    com = any(str(x).lower().startswith("la communication") for x in v)
    ges = any(str(x).lower().startswith("la gestion") for x in v)
    if com and ges:
        return "mixte"
    if com:
        return "communication"
    if ges:
        return "gestion"
    return "autre"


def parse_level(v: Any) -> float:
    if isinstance(v, str) and v.lower().startswith("niveau"):
        try:
            return float(v.split()[1])
        except Exception:
            return np.nan
    return np.nan


def parse_year(v: Any) -> float:
    if isinstance(v, str):
        try:
            return float(v[:4])
        except Exception:
            return np.nan
    return np.nan


def build_dataset(raw: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """Ajoute toutes les variables dérivées. Ne modifie pas `raw`."""
    df = raw.copy()
    g = plan["general"]
    lo, hi = g["likert"]["min"], g["likert"]["max"]
    mf = g["min_items_fraction"]

    # --- éligibilité
    df["consent_ok"] = df.get("consent", pd.Series(index=df.index, dtype=object)).map(lambda v: isinstance(v, str) and v.lower().startswith("oui"))
    df["declared_ok"] = df.get("declared", pd.Series(index=df.index, dtype=object)).map(lambda v: _yes(v) is True)
    df["project_ok"] = df.get("has_project", pd.Series(index=df.index, dtype=object)).map(lambda v: _yes(v) is True)

    # --- issue
    res = df.apply(lambda r: classify_outcome(r, plan), axis=1)
    df["issue"] = res.map(lambda t: t[0])
    df["issue_flags"] = res.map(lambda t: t[1])
    df["issue_label"] = df["issue"].map(OUTCOME_LABELS)
    df["echec"] = df["issue"].map({"succes": 0.0, "echec_partiel": 1.0, "echec_total": 1.0})
    df["issue_ord"] = df["issue"].map({"succes": 0.0, "echec_partiel": 1.0, "echec_total": 2.0})
    df["echec_total_vs_succes"] = df["issue"].map({"succes": 0.0, "echec_total": 1.0})

    # --- scores des constructs
    for name, c in plan["constructs"].items():
        df[name] = _scale_score(df, c["items"], c.get("reverse", []), lo, hi, mf)
    # orientation « risque » (haut = plus de risque d'échec), cohérente avec les hypothèses H1, H2, H5
    df["competences_risque"] = (lo + hi) - df["competences"]
    df["communication_risque"] = (lo + hi) - df["communication"]

    # mesure objective des compétences (protocole 3.5 : vérification objective si possible)
    hab = pd.to_numeric(df.get("comp_habitues"), errors="coerce")
    nb = pd.to_numeric(df.get("comp_nb_employes"), errors="coerce")
    ratio = hab / nb.where(nb > 0)
    df["part_habitues"] = ratio.clip(0, 1)
    df.loc[(hab > nb) & nb.notna(), "part_habitues"] = np.nan  # incohérence (habitués > employés)
    df["formation_ok"] = df.get("formation", pd.Series(index=df.index, dtype=object)).map(lambda v: {True: 1.0, False: 0.0, None: np.nan}[_yes(v)])

    # --- formalisation
    df["formalisation_idx"] = formalisation_index(df, plan)
    df["formalisation_cat"] = formalisation_category(df["formalisation_idx"], plan)
    df["famille"] = famille_flag(df)

    # --- contrôles
    df["taille_g"] = _map_group(df.get("taille", pd.Series(index=df.index, dtype=object)), plan["groups"]["taille"])
    df["secteur_g"] = _map_group(df.get("secteur", pd.Series(index=df.index, dtype=object)), plan["groups"]["secteur"])
    df["porteur_g"] = _map_group(df.get("porteur", pd.Series(index=df.index, dtype=object)), plan["groups"]["porteur"])
    anc = pd.to_numeric(df.get("anciennete"), errors="coerce").clip(lower=0)
    df["anciennete_log"] = np.log1p(anc)
    df["type_projet"] = df.get("projet_type", pd.Series(index=df.index, dtype=object)).map(type_projet)
    df["digit_niveau_num"] = df.get("digit_niveau", pd.Series(index=df.index, dtype=object)).map(parse_level)
    df["mois_usage_num"] = pd.to_numeric(df.get("mois_usage"), errors="coerce")
    df["annee_debut"] = df.get("start_year", pd.Series(index=df.index, dtype=object)).map(parse_year)
    df["usage_classe"] = df.get("usage_taux", pd.Series(index=df.index, dtype=object)).map(rate_class)

    # --- population analysable
    df["analysable"] = df["consent_ok"] & df["declared_ok"] & df["project_ok"] & df["issue"].isin(OUTCOME_ORDER) & df["_completed"].fillna(True).astype(bool)
    return df


def add_z(df: pd.DataFrame, cols: dict[str, str]) -> pd.DataFrame:
    """Ajoute des colonnes centrées-réduites (nom_z) calculées sur le sous-échantillon fourni."""
    out = df.copy()
    for src, dst in cols.items():
        out[dst] = _zscore(pd.to_numeric(out[src], errors="coerce"))
    return out
