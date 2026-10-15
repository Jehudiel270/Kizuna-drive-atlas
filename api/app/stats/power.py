"""Puissance : plus petit rapport de cotes détectable (approximation de Hsieh et al., 1998, prédicteur centré-réduit)."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def r2_on_others(x: np.ndarray, others: np.ndarray) -> float:
    if others.size == 0 or len(x) < 5:
        return 0.0
    Z = np.column_stack([np.ones(len(x)), others])
    beta, *_ = np.linalg.lstsq(Z, x, rcond=None)
    resid = x - Z @ beta
    ss = float(np.sum((x - x.mean()) ** 2))
    return 1 - float(np.sum(resid ** 2)) / ss if ss > 0 else 0.0


def min_detectable_or(n: int, prevalence: float, r2_others: float = 0.0, alpha: float = 0.05, power: float = 0.8) -> float:
    """OR par écart-type du prédicteur détectable avec la puissance voulue (test bilatéral)."""
    if n <= 0 or not 0 < prevalence < 1:
        return float("nan")
    za = stats.norm.ppf(1 - alpha / 2)
    zb = stats.norm.ppf(power)
    var = n * prevalence * (1 - prevalence) * (1 - min(r2_others, 0.99))
    return float(math.exp((za + zb) / math.sqrt(var)))


def power_for_or(n: int, prevalence: float, or_: float, r2_others: float = 0.0, alpha: float = 0.05) -> float:
    if n <= 0 or not 0 < prevalence < 1 or or_ <= 0:
        return float("nan")
    za = stats.norm.ppf(1 - alpha / 2)
    se = 1 / math.sqrt(n * prevalence * (1 - prevalence) * (1 - min(r2_others, 0.99)))
    z = abs(math.log(or_)) / se
    return float(stats.norm.cdf(z - za) + stats.norm.cdf(-z - za))
