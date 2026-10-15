"""Régression logistique pénalisée de Firth (réduction du biais, estimations finies en cas de séparation).

Heinze & Schemper (2002) ; mêmes équations que `logistf` : score modifié par la diagonale de la matrice chapeau,
demi-pas de Newton et plafonnement du pas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.special import expit


@dataclass
class FirthResult:
    beta: np.ndarray
    cov: np.ndarray
    loglik: float          # log-vraisemblance non pénalisée aux estimations
    loglik_pen: float      # log-vraisemblance pénalisée (utilisée pour les tests du rapport de vraisemblance)
    converged: bool
    n_iter: int


def _loglik(X: np.ndarray, y: np.ndarray, beta: np.ndarray) -> float:
    eta = X @ beta
    return float(np.sum(y * eta - np.logaddexp(0.0, eta)))


def _pen_loglik(X: np.ndarray, y: np.ndarray, beta: np.ndarray) -> float:
    eta = X @ beta
    p = expit(eta)
    w = p * (1 - p)
    xtwx = X.T @ (w[:, None] * X)
    sign, logdet = np.linalg.slogdet(xtwx)
    if sign <= 0:
        return -np.inf
    return float(np.sum(y * eta - np.logaddexp(0.0, eta)) + 0.5 * logdet)


def firth_logit(X: np.ndarray, y: np.ndarray, max_iter: int = 200, tol: float = 1e-8, max_step: float = 5.0) -> FirthResult:
    """X : matrice de conception AVEC colonne de constante en première position."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n, k = X.shape
    beta = np.zeros(k)
    pbar = min(max(float(y.mean()), 1e-6), 1 - 1e-6)
    beta[0] = math.log(pbar / (1 - pbar))
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        eta = X @ beta
        p = expit(eta)
        w = p * (1 - p)
        xtwx = X.T @ (w[:, None] * X)
        try:
            inv = np.linalg.inv(xtwx)
        except np.linalg.LinAlgError:
            inv = np.linalg.pinv(xtwx)
        h = w * np.einsum("ij,jk,ik->i", X, inv, X)
        u = X.T @ (y - p + h * (0.5 - p))
        step = inv @ u
        mx = float(np.max(np.abs(step)))
        if mx > max_step:
            step *= max_step / mx
        cur = _pen_loglik(X, y, beta)
        for _ in range(15):
            if _pen_loglik(X, y, beta + step) >= cur - 1e-10:
                break
            step = step / 2.0
        beta = beta + step
        if float(np.max(np.abs(step))) < tol and float(np.max(np.abs(u))) < 1e-5:
            converged = True
            break
    eta = X @ beta
    p = expit(eta)
    w = p * (1 - p)
    xtwx = X.T @ (w[:, None] * X)
    cov = np.linalg.inv(xtwx)
    return FirthResult(beta, cov, _loglik(X, y, beta), _pen_loglik(X, y, beta), converged, it)
