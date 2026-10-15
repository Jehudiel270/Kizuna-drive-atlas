"""Statistiques descriptives et comparaisons de groupes (ANOVA / Khi², protocole 5.1–5.2)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from ..core.constructs import OUTCOME_LABELS, OUTCOME_ORDER

CAT_VARS = {
    "issue": "Issue du projet",
    "secteur_g": "Secteur (regroupé)",
    "taille_g": "Taille de l'entreprise",
    "ville": "Ville",
    "mode": "Mode de passation",
    "type_projet": "Type de projet",
    "porteur_g": "Porteur du projet",
    "formalisation_cat": "Formalisation",
    "famille": "Gouvernance familiale",
    "digit_niveau_num": "Niveau de digitalisation avant projet",
    "annee_debut": "Année de démarrage",
    "financement": "Financement",
    "sur_mesure": "Outil sur mesure",
    "formation": "Formation des utilisateurs",
    "role": "Rôle du répondant",
}
SCORE_VARS = {
    "gouvernance": "Gouvernance centralisée (1–5)",
    "competences": "Compétences numériques (1–5)",
    "communication": "Communication interne (1–5)",
    "soutien": "Soutien de la direction (1–5)",
    "formalisation_idx": "Indice de formalisation (0–1)",
    "outil_adequation": "Adéquation / simplicité de l'outil (1–5)",
    "part_habitues": "Part d'employés habitués au numérique (0–1)",
    "formation_heures": "Heures de formation par personne",
    "mois_usage_num": "Mois d'usage de l'outil",
    "anciennete": "Ancienneté de l'entreprise (années)",
}


def _label_value(var: str, v: Any) -> Any:
    if var == "famille":
        return {1.0: "Familiale", 0.0: "Non familiale"}.get(v, v)
    if var == "digit_niveau_num":
        return f"Niveau {int(v)}" if pd.notna(v) else v
    if var == "annee_debut":
        return str(int(v)) if pd.notna(v) else v
    if var == "issue":
        return OUTCOME_LABELS.get(v, v)
    return v


def freq_table(s: pd.Series, var: str = "") -> list[dict]:
    s = s.dropna()
    vc = s.value_counts()
    tot = int(vc.sum()) or 1
    return [{"value": str(_label_value(var, k)), "n": int(v), "pct": float(v / tot)} for k, v in vc.items()]


def profile(df: pd.DataFrame) -> dict:
    base = df[df["analysable"]]
    out: dict[str, Any] = {"n": int(len(base)), "variables": {}}
    for var, title in CAT_VARS.items():
        if var not in base:
            continue
        s = base[var]
        if var == "annee_debut":
            s = s.map(lambda x: x)
        t = freq_table(s.sort_values() if var in ("digit_niveau_num", "annee_debut") else s, var)
        if var in ("digit_niveau_num", "annee_debut"):
            t = sorted(t, key=lambda r: r["value"])
        out["variables"][var] = {"title": title, "missing": int(s.isna().sum()), "table": t}
    return out


def likert_items(df: pd.DataFrame, plan: dict, labels: dict[str, str]) -> list[dict]:
    base = df[df["analysable"]]
    lo, hi = plan["general"]["likert"]["min"], plan["general"]["likert"]["max"]
    out = []
    for cname, c in plan["constructs"].items():
        for it in c["items"] + (["gov_liens"] if cname == "gouvernance" else []):
            if it not in base:
                continue
            s = pd.to_numeric(base[it], errors="coerce").dropna()
            counts = [int((s == v).sum()) for v in range(lo, hi + 1)]
            out.append({"construct": cname, "construct_label": c["label"], "name": it, "label": labels.get(it, it), "n": int(len(s)),
                        "counts": counts, "mean": float(s.mean()) if len(s) else None, "sd": float(s.std(ddof=1)) if len(s) > 1 else None,
                        "median": float(s.median()) if len(s) else None, "reversed": it in c.get("reverse", [])})
    for it in ("env_coupures", "env_pression", "gov_liens"):
        if it in base and not any(o["name"] == it for o in out):
            s = pd.to_numeric(base[it], errors="coerce").dropna()
            counts = [int((s == v).sum()) for v in range(lo, hi + 1)]
            out.append({"construct": "contexte", "construct_label": "Contexte (variables de contrôle TOE)", "name": it, "label": labels.get(it, it),
                        "n": int(len(s)), "counts": counts, "mean": float(s.mean()) if len(s) else None,
                        "sd": float(s.std(ddof=1)) if len(s) > 1 else None, "median": float(s.median()) if len(s) else None, "reversed": False})
    return out


def histogram(s: pd.Series, bins: int = 10) -> dict:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) == 0:
        return {"edges": [], "counts": []}
    counts, edges = np.histogram(s, bins=bins)
    return {"edges": [float(e) for e in edges], "counts": [int(c) for c in counts]}


def scores_by_issue(df: pd.DataFrame, seed: int = 1) -> list[dict]:
    base = df[df["analysable"]]
    out = []
    for var, title in SCORE_VARS.items():
        if var not in base:
            continue
        s = pd.to_numeric(base[var], errors="coerce")
        groups = {g: s[base["issue"] == g].dropna() for g in OUTCOME_ORDER}
        valid = {g: v for g, v in groups.items() if len(v) >= 2}
        row: dict[str, Any] = {"var": var, "title": title, "n": int(s.notna().sum()), "histogram": histogram(s),
                               "overall": {"mean": float(s.mean()) if s.notna().any() else None, "sd": float(s.std(ddof=1)) if s.notna().sum() > 1 else None,
                                           "median": float(s.median()) if s.notna().any() else None},
                               "groups": [{"issue": g, "label": OUTCOME_LABELS[g], "n": int(len(groups[g])),
                                           "mean": float(groups[g].mean()) if len(groups[g]) else None,
                                           "sd": float(groups[g].std(ddof=1)) if len(groups[g]) > 1 else None,
                                           "median": float(groups[g].median()) if len(groups[g]) else None} for g in OUTCOME_ORDER],
                               "anova": None, "kruskal": None, "posthoc": []}
        if len(valid) >= 2:
            vals = list(valid.values())
            F, p = stats.f_oneway(*vals)
            allv = np.concatenate([v.to_numpy() for v in vals])
            grand = allv.mean()
            ssb = sum(len(v) * (v.mean() - grand) ** 2 for v in vals)
            sst = float(((allv - grand) ** 2).sum())
            row["anova"] = {"F": float(F), "p": float(p), "df1": len(vals) - 1, "df2": int(len(allv) - len(vals)), "eta2": float(ssb / sst) if sst > 0 else None}
            H, pk = stats.kruskal(*vals)
            row["kruskal"] = {"H": float(H), "p": float(pk)}
            if p < 0.05 and len(vals) >= 2:
                lab = np.concatenate([[g] * len(v) for g, v in valid.items()])
                tk = pairwise_tukeyhsd(allv, lab)
                for r in tk.summary().data[1:]:
                    row["posthoc"].append({"a": OUTCOME_LABELS.get(r[0], r[0]), "b": OUTCOME_LABELS.get(r[1], r[1]), "diff": float(r[2]), "p": float(r[3]), "reject": bool(r[6])})
        out.append(row)
    return out


def cramers_v_corrected(chi2: float, n: int, r: int, k: int) -> float:
    if n <= 1 or min(r, k) < 2:
        return float("nan")
    phi2 = chi2 / n
    phi2c = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rc = r - (r - 1) ** 2 / (n - 1)
    kc = k - (k - 1) ** 2 / (n - 1)
    d = min(kc - 1, rc - 1)
    return float(math.sqrt(phi2c / d)) if d > 0 else float("nan")


def mc_chi2_pvalue(table: np.ndarray, B: int = 4000, seed: int = 3) -> float:
    rng = np.random.default_rng(seed)
    obs = stats.chi2_contingency(table, correction=False)[0]
    rows = np.repeat(np.arange(table.shape[0]), table.sum(axis=1))
    cols = np.repeat(np.arange(table.shape[1]), table.sum(axis=0))
    count = 0
    for _ in range(B):
        perm = rng.permutation(cols)
        t = np.zeros_like(table)
        np.add.at(t, (rows, perm), 1)
        if t.sum(axis=0).min() == 0 or t.sum(axis=1).min() == 0:
            continue
        if stats.chi2_contingency(t, correction=False)[0] >= obs - 1e-9:
            count += 1
    return float((count + 1) / (B + 1))


def crosstab_test(df: pd.DataFrame, var: str, by: str = "issue") -> dict:
    base = df[df["analysable"]].copy()
    if var not in base:
        return {"var": var, "error": "variable inconnue"}
    s = base[var].map(lambda v: _label_value(var, v))
    d = pd.DataFrame({"row": s, "col": base[by].map(lambda v: OUTCOME_LABELS.get(v, v))}).dropna()
    if d.empty:
        return {"var": var, "title": CAT_VARS.get(var, var), "n": 0, "table": [], "columns": []}
    tab = pd.crosstab(d["row"], d["col"])
    cols = [OUTCOME_LABELS[o] for o in OUTCOME_ORDER if OUTCOME_LABELS[o] in tab.columns]
    tab = tab[cols]
    res: dict[str, Any] = {"var": var, "title": CAT_VARS.get(var, var), "n": int(tab.values.sum()), "columns": cols, "table": [], "test": None}
    for idx, r in tab.iterrows():
        tot = int(r.sum())
        res["table"].append({"value": str(idx), "counts": [int(x) for x in r.values], "total": tot,
                             "row_pct": [float(x / tot) if tot else None for x in r.values]})
    if tab.shape[0] >= 2 and tab.shape[1] >= 2 and tab.values.sum() >= 5:
        chi2, p, dof, exp = stats.chi2_contingency(tab.values, correction=False)
        low = float((exp < 5).mean())
        res["test"] = {"chi2": float(chi2), "dof": int(dof), "p": float(p), "cramers_v": cramers_v_corrected(chi2, int(tab.values.sum()), *tab.shape),
                       "low_expected_share": low, "mc_p": None}
        if low > 0.2:
            res["test"]["mc_p"] = mc_chi2_pvalue(tab.values)
            res["test"]["warning"] = "Plus de 20 % des effectifs théoriques sont < 5 : p-valeur de Monte-Carlo fournie à la place du Khi² asymptotique."
    return res


def all_crosstabs(df: pd.DataFrame) -> list[dict]:
    out = []
    for var in CAT_VARS:
        if var == "issue":
            continue
        ct = crosstab_test(df, var)
        if ct.get("n", 0) > 0:
            out.append(ct)
    return out
