"""Courbes d'interaction : probabilité prédite d'échec (standardisation marginale sur l'échantillon) selon un facteur et un modérateur."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy.special import expit

GRID = np.linspace(-2.0, 2.0, 17)


def _recompute_interactions(X: pd.DataFrame) -> pd.DataFrame:
    for col in X.columns:
        if ":" in col:
            parts = col.split(":")
            if all(p in X.columns for p in parts):
                v = np.ones(len(X))
                for p in parts:
                    v = v * X[p].to_numpy(float)
                X[col] = v
    return X


def _p(fit, X: pd.DataFrame) -> float:
    beta = fit.params.reindex(X.columns).fillna(0.0).to_numpy(float)
    return float(expit(X.to_numpy(float) @ beta).mean())


def continuous_moderator(fit, factor: str, moderator: str = "z_soutien", levels: dict[str, float] | None = None) -> list[dict]:
    if fit is None or fit.X is None or factor not in fit.X.columns or moderator not in fit.X.columns:
        return []
    levels = levels or {"Soutien faible (−1 ET)": -1.0, "Soutien élevé (+1 ET)": 1.0}
    out = []
    for name, lv in levels.items():
        pts = []
        for v in GRID:
            X = fit.X.copy()
            X[factor] = v
            X[moderator] = lv
            X = _recompute_interactions(X)
            pts.append({"x": float(v), "p": _p(fit, X)})
        out.append({"level": name, "points": pts})
    return out


def categorical_moderator(fit, factor: str, categories: list[str]) -> list[dict]:
    """Courbes de P(échec) selon la gouvernance pour chaque catégorie (colonnes indicatrices `[T.cat]`)."""
    if fit is None or fit.X is None or factor not in fit.X.columns:
        return []
    dummy_cols = {c: re.search(r"\[T\.([^\]]+)\]$", c).group(1) for c in fit.X.columns if ":" not in c and re.search(r"\[T\.([^\]]+)\]$", c)}
    out = []
    for cat in categories:
        pts = []
        for v in GRID:
            X = fit.X.copy()
            X[factor] = v
            for c, lab in dummy_cols.items():
                X[c] = 1.0 if lab == cat else 0.0
            X = _recompute_interactions(X)
            pts.append({"x": float(v), "p": _p(fit, X)})
        out.append({"level": cat, "points": pts})
    return out
