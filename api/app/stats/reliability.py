"""Fiabilité des échelles multi-items : alpha de Cronbach (seuil 0,70, protocole 4.10), oméga, corrélations item-reste."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.decomposition import FactorAnalysis


def cronbach_alpha(M: np.ndarray) -> float:
    M = np.asarray(M, dtype=float)
    k = M.shape[1]
    if k < 2 or M.shape[0] < 3:
        return float("nan")
    item_var = M.var(axis=0, ddof=1)
    total_var = M.sum(axis=1).var(ddof=1)
    if total_var <= 0:
        return float("nan")
    return float(k / (k - 1) * (1 - item_var.sum() / total_var))


def alpha_ci(M: np.ndarray, B: int = 1000, seed: int = 11) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = M.shape[0]
    vals = []
    for _ in range(B):
        idx = rng.integers(0, n, n)
        a = cronbach_alpha(M[idx])
        if not math.isnan(a):
            vals.append(a)
    if len(vals) < 50:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def omega_total(M: np.ndarray) -> float:
    M = np.asarray(M, dtype=float)
    if M.shape[1] < 3 or M.shape[0] < 10:
        return float("nan")
    Z = (M - M.mean(axis=0)) / M.std(axis=0, ddof=1)
    try:
        fa = FactorAnalysis(n_components=1, random_state=0).fit(Z)
    except Exception:
        return float("nan")
    lam = np.abs(fa.components_[0])
    psi = fa.noise_variance_
    return float(lam.sum() ** 2 / (lam.sum() ** 2 + psi.sum()))


def construct_reliability(df: pd.DataFrame, plan: dict, labels: dict[str, str]) -> list[dict]:
    lo, hi = plan["general"]["likert"]["min"], plan["general"]["likert"]["max"]
    thr = plan["general"]["cronbach_min"]
    base = df[df["consent_ok"] & df["declared_ok"] & df["project_ok"]]
    out = []
    for name, c in plan["constructs"].items():
        items = c["items"]
        cols = []
        for it in items:
            s = pd.to_numeric(base.get(it), errors="coerce")
            if it in c.get("reverse", []):
                s = (lo + hi) - s
            cols.append(s.rename(it))
        M = pd.concat(cols, axis=1).dropna()
        n = len(M)
        k = len(items)
        res = {"construct": name, "label": c["label"], "note": c.get("note"), "n": n, "k": k, "threshold": thr, "items": [], "alpha": None,
               "alpha_ci": [None, None], "omega": None, "mean_interitem_r": None, "spearman_brown": None, "status": "non_calculable"}
        if n < 10 or k < 2:
            res["status_text"] = "Effectif insuffisant pour estimer la fiabilité (n < 10)."
            out.append(res)
            continue
        A = M.to_numpy(float)
        a = cronbach_alpha(A)
        lo_ci, hi_ci = alpha_ci(A) if n >= 20 else (float("nan"), float("nan"))
        corr = np.corrcoef(A, rowvar=False)
        iu = np.triu_indices(k, 1)
        mir = float(np.nanmean(corr[iu]))
        res.update({"alpha": a, "alpha_ci": [lo_ci, hi_ci], "omega": omega_total(A), "mean_interitem_r": mir})
        if k == 2:
            res["spearman_brown"] = float(2 * mir / (1 + mir)) if (1 + mir) != 0 else None
            res["status_text"] = "Échelle à 2 items : l'alpha est peu fiable ; on lit surtout la corrélation inter-items et Spearman-Brown."
        for j, it in enumerate(items):
            rest = np.delete(A, j, axis=1).sum(axis=1)
            ir = float(np.corrcoef(A[:, j], rest)[0, 1]) if n > 2 else float("nan")
            ad = cronbach_alpha(np.delete(A, j, axis=1)) if k > 2 else float("nan")
            res["items"].append({"name": it, "label": labels.get(it, it), "reversed": it in c.get("reverse", []), "mean": float(A[:, j].mean()),
                                 "sd": float(A[:, j].std(ddof=1)), "item_rest_r": ir, "alpha_if_deleted": ad})
        ref = a if k > 2 else (res["spearman_brown"] if res["spearman_brown"] is not None else a)
        res["status"] = "ok" if (ref is not None and not math.isnan(ref) and ref >= thr) else "faible"
        if res["status"] == "faible":
            res["status_text"] = (res.get("status_text") or "") + f" Fiabilité inférieure au seuil de {thr:.2f} fixé par le protocole : à discuter (retrait d'item, score à interpréter avec prudence)."
        elif not res.get("status_text"):
            res["status_text"] = f"Fiabilité conforme au seuil de {thr:.2f} du protocole."
        out.append(res)
    return out
