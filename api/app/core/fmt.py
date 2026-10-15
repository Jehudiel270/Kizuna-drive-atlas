"""Formatage français (virgule décimale) et conversion JSON sûre."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def fnum(x: float | None, d: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x))):
        return "—"
    if isinstance(x, float) and math.isinf(x):
        return "∞"
    return f"{x:.{d}f}".replace(".", ",")


def fp(p: float | None) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "p = —"
    if p < 0.001:
        return "p < 0,001"
    return "p = " + f"{p:.3f}".replace(".", ",")


def fpct(x: float | None, d: int = 0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return fnum(100 * x, d) + " %"


def jsonable(o: Any) -> Any:
    """Convertit récursivement numpy/pandas en types JSON ; NaN/inf -> None."""
    if o is None:
        return None
    if isinstance(o, (str, bool)):
        return o
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(o, int):
        return o
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return [jsonable(v) for v in o.tolist()]
    if isinstance(o, pd.Series):
        return {str(k): jsonable(v) for k, v in o.to_dict().items()}
    if isinstance(o, pd.DataFrame):
        return [jsonable(r) for r in o.to_dict(orient="records")]
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if o is pd.NaT:
        return None
    return str(o)
