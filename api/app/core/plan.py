"""Chargement, fusion et empreinte du plan d'analyse et du codebook."""
from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=1)
def _default_plan() -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / "plan.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _default_codebook() -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / "codebook.yaml").read_text(encoding="utf-8"))


def default_plan_text() -> str:
    return (CONFIG_DIR / "plan.yaml").read_text(encoding="utf-8")


def default_codebook_text() -> str:
    return (CONFIG_DIR / "codebook.yaml").read_text(encoding="utf-8")


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def get_plan(override: dict | None = None) -> dict[str, Any]:
    plan = copy.deepcopy(_default_plan())
    if override:
        plan = deep_merge(plan, override)
    return plan


def get_codebook(override: dict | None = None) -> dict[str, Any]:
    cb = copy.deepcopy(_default_codebook())
    if override and override.get("variables"):
        cb = override
    return cb


def stable_hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def validate_plan(plan: dict) -> list[str]:
    """Contrôles minimaux de cohérence ; renvoie la liste des erreurs."""
    errors: list[str] = []
    g = plan.get("general", {})
    if not 0 < g.get("alpha", 0) < 1:
        errors.append("general.alpha doit être entre 0 et 1")
    tn = g.get("target_n", {})
    if tn.get("min", 0) > tn.get("max", 0):
        errors.append("general.target_n.min doit être ≤ max")
    for name, c in plan.get("constructs", {}).items():
        if not c.get("items"):
            errors.append(f"constructs.{name}.items est vide")
        for r in c.get("reverse", []):
            if r not in c["items"]:
                errors.append(f"constructs.{name}.reverse contient {r} absent de items")
    th = plan.get("formalisation", {}).get("thresholds", {})
    if th.get("informel_lt", 0) >= th.get("formel_ge", 1):
        errors.append("formalisation.thresholds : informel_lt doit être < formel_ge")
    ids = [h.get("id") for h in plan.get("hypotheses", [])]
    if len(ids) != len(set(ids)):
        errors.append("hypotheses : identifiants dupliqués")
    return errors
