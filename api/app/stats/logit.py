"""Ajustement de modèles logistiques (binaire, ordinal) avec bascule vers Firth et diagnostics."""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy import stats
from statsmodels.miscmodels.ordinal_model import OrderedModel

from .firth import firth_logit


@dataclass
class ModelFit:
    kind: str                       # "binary" | "ordinal"
    method: str                     # "ML" | "Firth" | "ML-ordinal"
    names: list[str]                # termes (hors constante / seuils)
    params: pd.Series
    bse: pd.Series
    cov: pd.DataFrame
    llf: float                      # log-vraisemblance (pénalisée si Firth)
    llf_plain: float                # log-vraisemblance non pénalisée
    llnull: float
    nobs: int
    k: int                          # nombre de coefficients (hors constante)
    events: int
    fitted: np.ndarray | None = None
    y: np.ndarray | None = None
    X: pd.DataFrame | None = None
    converged: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def pvalues(self) -> pd.Series:
        z = self.params / self.bse
        return pd.Series(2 * stats.norm.sf(np.abs(z)), index=self.params.index)

    def row(self, term: str) -> dict:
        b, se = float(self.params[term]), float(self.bse[term])
        z = b / se if se > 0 else float("nan")
        p = float(2 * stats.norm.sf(abs(z))) if se > 0 else float("nan")
        return {
            "term": term,
            "coef": b,
            "se": se,
            "or": float(math.exp(b)) if abs(b) < 50 else float("inf"),
            "ci_low": float(math.exp(b - 1.959964 * se)) if abs(b) < 50 else float("nan"),
            "ci_high": float(math.exp(b + 1.959964 * se)) if abs(b) < 50 else float("nan"),
            "z": z,
            "p": p,
        }


def _separation(params: np.ndarray, bse: np.ndarray) -> bool:
    if not np.all(np.isfinite(params)) or not np.all(np.isfinite(bse)):
        return True
    return bool(np.max(np.abs(params)) > 12 or np.max(bse) > 1e3)


def _binary_design(formula: str, data: pd.DataFrame):
    y, X = patsy.dmatrices(formula, data, return_type="dataframe", NA_action="drop")
    return y.iloc[:, 0].to_numpy(dtype=float), X


def fit_binary(formula: str, data: pd.DataFrame, method: str = "auto", epv_min: float = 10.0) -> ModelFit:
    """method : 'auto' (Firth si EPV < epv_min ou séparation), 'ml', 'firth'."""
    y, X = _binary_design(formula, data)
    n = len(y)
    events = int(y.sum())
    k = X.shape[1] - 1
    notes: list[str] = []
    epv = min(events, n - events) / max(k, 1)
    use_firth = method == "firth" or (method == "auto" and epv < epv_min)
    res_ml = None
    if not use_firth:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                res_ml = sm.Logit(y, X).fit(disp=0, maxiter=200)
            except Exception as e:  # séparation parfaite, matrice singulière…
                notes.append(f"ML non convergent ({type(e).__name__}) : bascule vers Firth")
                res_ml = None
            else:
                if _separation(res_ml.params.to_numpy(), res_ml.bse.to_numpy()) or not bool(res_ml.mle_retvals.get("converged", True)):
                    notes.append("Séparation quasi-parfaite détectée : bascule vers Firth")
                    res_ml = None
        if res_ml is None and method == "ml":
            raise RuntimeError("Estimation par maximum de vraisemblance impossible : " + "; ".join(notes))
    if res_ml is not None:
        null = sm.Logit(y, np.ones((n, 1))).fit(disp=0)
        params = pd.Series(res_ml.params.to_numpy(), index=X.columns)
        bse = pd.Series(res_ml.bse.to_numpy(), index=X.columns)
        cov = pd.DataFrame(res_ml.cov_params().to_numpy(), index=X.columns, columns=X.columns)
        fitted = res_ml.predict(X).to_numpy()
        fit = ModelFit("binary", "ML", [c for c in X.columns if c != "Intercept"], params, bse, cov,
                       float(res_ml.llf), float(res_ml.llf), float(null.llf), n, k, events, fitted, y, X, True, notes)
        return fit
    # Firth
    if method == "auto" and epv < epv_min:
        notes.append(f"EPV = {epv:.1f} < {epv_min:g} : régression pénalisée de Firth utilisée (estimations moins biaisées)")
    fr = firth_logit(X.to_numpy(), y)
    null = firth_logit(np.ones((n, 1)), y)
    params = pd.Series(fr.beta, index=X.columns)
    cov = pd.DataFrame(fr.cov, index=X.columns, columns=X.columns)
    bse = pd.Series(np.sqrt(np.diag(fr.cov)), index=X.columns)
    from scipy.special import expit
    fitted = expit(X.to_numpy() @ fr.beta)
    if not fr.converged:
        notes.append("Firth : convergence non atteinte dans le nombre d'itérations imparti")
    return ModelFit("binary", "Firth", [c for c in X.columns if c != "Intercept"], params, bse, cov,
                    fr.loglik_pen, fr.loglik, null.loglik_pen, n, k, events, fitted, y, X, fr.converged, notes)


def fit_ordinal(formula_rhs: str, data: pd.DataFrame, outcome: str) -> ModelFit:
    """Logit à cotes proportionnelles (statsmodels OrderedModel). `formula_rhs` sans constante."""
    d = data.dropna(subset=[outcome]).copy()
    X = patsy.dmatrix(formula_rhs, d, return_type="dataframe", NA_action="drop")
    X = X.drop(columns=["Intercept"], errors="ignore")
    y = d.loc[X.index, outcome].astype(int)
    n = len(y)
    mod = OrderedModel(y.to_numpy(), X.to_numpy(), distr="logit")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = mod.fit(method="bfgs", disp=False, maxiter=2000)
    k = X.shape[1]
    cov_full = np.asarray(res.cov_params())
    names = list(X.columns)
    params = pd.Series(np.asarray(res.params)[:k], index=names)
    bse = pd.Series(np.asarray(res.bse)[:k], index=names)
    cov = pd.DataFrame(cov_full[:k, :k], index=names, columns=names)
    # modèle nul : seuils seuls (fréquences observées)
    counts = y.value_counts(normalize=True)
    llnull = float(sum(int((y == c).sum()) * math.log(p) for c, p in counts.items()))
    notes = [] if bool(res.mle_retvals.get("converged", True)) else ["Modèle ordinal : convergence douteuse"]
    return ModelFit("ordinal", "ML-ordinal", names, params, bse, cov, float(res.llf), float(res.llf), llnull, n, k,
                    int((y > 0).sum()), None, y.to_numpy(), X, True, notes)


def lr_test(full: ModelFit, reduced: ModelFit) -> dict:
    df = full.k - reduced.k
    stat = max(0.0, 2 * (full.llf - reduced.llf))
    p = float(stats.chi2.sf(stat, df)) if df > 0 else float("nan")
    return {"stat": float(stat), "df": int(df), "p": p}


# ---------------------------------------------------------------------------------- diagnostics

def auc_score(y: np.ndarray, p: np.ndarray) -> float:
    ranks = stats.rankdata(p)
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def roc_points(y: np.ndarray, p: np.ndarray, max_points: int = 60) -> list[dict]:
    order = np.argsort(-p)
    ys = y[order]
    tps = np.cumsum(ys)
    fps = np.cumsum(1 - ys)
    tpr = tps / max(ys.sum(), 1)
    fpr = fps / max((1 - ys).sum(), 1)
    idx = np.unique(np.linspace(0, len(ys) - 1, min(max_points, len(ys))).astype(int))
    pts = [{"fpr": 0.0, "tpr": 0.0}] + [{"fpr": float(fpr[i]), "tpr": float(tpr[i])} for i in idx]
    return pts


def hosmer_lemeshow(y: np.ndarray, p: np.ndarray, groups: int = 10) -> dict:
    df = pd.DataFrame({"y": y, "p": p})
    try:
        df["g"] = pd.qcut(df["p"].rank(method="first"), q=groups, labels=False, duplicates="drop")
    except ValueError:
        return {"stat": float("nan"), "df": 0, "p": float("nan"), "bins": []}
    agg = df.groupby("g").agg(n=("y", "size"), obs=("y", "sum"), exp=("p", "sum"), pbar=("p", "mean"))
    stat = float((((agg["obs"] - agg["exp"]) ** 2) / (agg["exp"] * (1 - agg["pbar"]).clip(lower=1e-9))).sum())
    dof = max(len(agg) - 2, 1)
    bins = [{"mean_pred": float(r.pbar), "obs_rate": float(r.obs / r.n), "n": int(r.n)} for r in agg.itertuples()]
    return {"stat": stat, "df": dof, "p": float(stats.chi2.sf(stat, dof)), "bins": bins}


def pseudo_r2(fit: ModelFit) -> dict:
    n = fit.nobs
    if fit.kind == "binary" and fit.y is not None and fit.fitted is not None:
        ll_model = float(np.sum(fit.y * np.log(np.clip(fit.fitted, 1e-12, 1)) + (1 - fit.y) * np.log(np.clip(1 - fit.fitted, 1e-12, 1))))
        pbar = fit.y.mean()
        ll_null = float(n * (pbar * math.log(pbar) + (1 - pbar) * math.log(1 - pbar))) if 0 < pbar < 1 else float("nan")
    else:
        ll_model, ll_null = fit.llf_plain, fit.llnull
    mcf = 1 - ll_model / ll_null if ll_null else float("nan")
    cs = 1 - math.exp((2 / n) * (ll_null - ll_model))
    nag = cs / (1 - math.exp((2 / n) * ll_null)) if (1 - math.exp((2 / n) * ll_null)) else float("nan")
    return {"mcfadden": float(mcf), "nagelkerke": float(nag)}


def vif_table(X: pd.DataFrame) -> list[dict]:
    cols = [c for c in X.columns if c != "Intercept"]
    out = []
    if len(cols) < 2:
        return out
    A = X[cols].to_numpy(dtype=float)
    for j, c in enumerate(cols):
        yj = A[:, j]
        others = np.delete(A, j, axis=1)
        Z = np.column_stack([np.ones(len(yj)), others])
        beta, *_ = np.linalg.lstsq(Z, yj, rcond=None)
        resid = yj - Z @ beta
        ss_tot = float(np.sum((yj - yj.mean()) ** 2))
        r2 = 1 - float(np.sum(resid ** 2)) / ss_tot if ss_tot > 0 else 0.0
        out.append({"term": c, "vif": float(1 / (1 - r2)) if r2 < 0.999999 else float("inf")})
    return out


def coef_table(fit: ModelFit, labels: dict[str, str] | None = None) -> list[dict]:
    rows = []
    for t in fit.names:
        r = fit.row(t)
        r["label"] = (labels or {}).get(t, t)
        rows.append(r)
    return rows


def diagnostics(fit: ModelFit) -> dict:
    d: dict[str, Any] = {
        "n": fit.nobs,
        "events": fit.events,
        "non_events": fit.nobs - fit.events,
        "k": fit.k,
        "epv": float(min(fit.events, fit.nobs - fit.events) / max(fit.k, 1)),
        "method": fit.method,
        "converged": fit.converged,
        "notes": fit.warnings,
        "loglik": fit.llf_plain,
        "aic": float(-2 * fit.llf_plain + 2 * (fit.k + 1)),
        "bic": float(-2 * fit.llf_plain + math.log(fit.nobs) * (fit.k + 1)),
    }
    d.update(pseudo_r2(fit))
    if fit.kind == "binary" and fit.y is not None and fit.fitted is not None:
        d["auc"] = auc_score(fit.y, fit.fitted)
        d["hosmer_lemeshow"] = hosmer_lemeshow(fit.y, fit.fitted)
        d["roc"] = roc_points(fit.y, fit.fitted)
        if fit.X is not None:
            d["vif"] = vif_table(fit.X)
    return d
