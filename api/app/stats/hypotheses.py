"""Tests de H1 à H5 conformément au plan d'analyse du protocole (régressions logistiques avec interactions)."""
from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd
import patsy
from scipy import stats

from ..core.constructs import add_z
from ..core.fmt import fnum, fp, jsonable
from . import logit as L
from .power import min_detectable_or, power_for_or, r2_on_others

CATEGORICAL = {"taille_g", "secteur_g", "porteur_g", "type_projet", "formalisation_cat"}
Z_SRC = {
    "anciennete_z": "anciennete_log",
    "digit_niveau_z": "digit_niveau_num",
    "outil_adequation_z": "outil_adequation",
    "env_coupures_z": "env_coupures",
    "env_pression_z": "env_pression",
}
TERM_LABELS = {
    "Intercept": "Constante",
    "z_gouvernance": "Gouvernance centralisée (+1 ET)",
    "z_competences_risque": "Faibles compétences numériques (+1 ET)",
    "z_communication_risque": "Faible communication interne (+1 ET)",
    "z_soutien": "Soutien de la direction (+1 ET)",
    "anciennete_z": "Ancienneté de l'entreprise (log, +1 ET)",
    "digit_niveau_z": "Niveau de digitalisation avant projet (+1 ET)",
    "outil_adequation_z": "Adéquation et simplicité de l'outil (+1 ET)",
    "env_coupures_z": "Coupures électricité/Internet (+1 ET)",
    "env_pression_z": "Pression externe pour lancer le projet (+1 ET)",
    "famille": "Gouvernance familiale (oui vs non)",
}
CAT_LABELS = {
    "taille_g": "Taille", "secteur_g": "Secteur", "porteur_g": "Porteur du projet", "type_projet": "Type de projet",
    "formalisation_cat": "Formalisation",
}
SPECS = [
    {"name": "Principal", "outcome": "binary", "controls": "base", "method": "auto", "min_months": None,
     "desc": "Échec (partiel ou total) vs succès ; contrôles du protocole ; Firth si EPV < 10"},
    {"name": "Maximum de vraisemblance", "outcome": "binary", "controls": "base", "method": "ml", "min_months": None,
     "desc": "Sans pénalisation"},
    {"name": "Firth (toujours)", "outcome": "binary", "controls": "base", "method": "firth", "min_months": None,
     "desc": "Régression pénalisée systématique"},
    {"name": "Ordinal (succès < partiel < total)", "outcome": "ordinal", "controls": "base", "method": "ml", "min_months": None,
     "desc": "Logit à cotes proportionnelles sur les 3 modalités"},
    {"name": "Échec total vs succès", "outcome": "total_vs_succes", "controls": "base", "method": "auto", "min_months": None,
     "desc": "Échecs partiels exclus"},
    {"name": "Contrôles étendus (TOE)", "outcome": "binary", "controls": "extended", "method": "auto", "min_months": None,
     "desc": "Ajoute digitalisation préalable, porteur, outil, coupures, pression externe"},
    {"name": "Projets ≥ 6 mois d'usage", "outcome": "binary", "controls": "base", "method": "auto", "min_months": 6,
     "desc": "Corroboration par l'utilisation effective à 6 mois (protocole 3.5)"},
]


# --------------------------------------------------------------------------------------------- utilitaires

def pretty_term(name: str) -> str:
    if name in TERM_LABELS:
        return TERM_LABELS[name]
    if ":" in name:
        return " × ".join(pretty_term(p) for p in name.split(":")).replace(" (+1 ET)", "")
    m = re.match(r"C\((\w+)(?:,.*?)?\)\[T\.(.+)\]", name)
    if m:
        return f"{CAT_LABELS.get(m.group(1), m.group(1))} : {m.group(2)}"
    return name


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted([(k, v) for k, v in pvals.items() if v is not None and not math.isnan(v)], key=lambda kv: kv[1])
    m = len(items)
    adj: dict[str, float] = {}
    running = 0.0
    for i, (k, p) in enumerate(items):
        val = min(1.0, (m - i) * p)
        running = max(running, val)
        adj[k] = running
    return adj


def build_frame(df: pd.DataFrame, plan: dict, spec: dict) -> tuple[pd.DataFrame, str, list[str]]:
    d = df[df["analysable"]].copy()
    if spec.get("min_months") is not None:
        d = d[pd.to_numeric(d["mois_usage_num"], errors="coerce") >= spec["min_months"]]
    oc = {"binary": "echec", "ordinal": "issue_ord", "total_vs_succes": "echec_total_vs_succes"}[spec["outcome"]]
    ctrl = list(plan["models"]["controls"])
    if spec["controls"] == "extended":
        ctrl += list(plan["models"]["extended_controls"])
    need = [oc, "gouvernance", "competences_risque", "communication_risque", "soutien"] + [Z_SRC.get(c, c) for c in ctrl]
    d = d.dropna(subset=[c for c in need if c in d.columns])
    zmap = {
        "gouvernance": "z_gouvernance", "competences_risque": "z_competences_risque",
        "communication_risque": "z_communication_risque", "soutien": "z_soutien",
    }
    for c in ctrl:
        if c in Z_SRC:
            zmap[Z_SRC[c]] = c
    d = add_z(d, zmap)
    return d, oc, ctrl


def usable_controls(ctrl: list[str], frame: pd.DataFrame) -> list[str]:
    out = []
    for c in ctrl:
        if c not in frame.columns:
            continue
        if c in CATEGORICAL:
            if frame[c].nunique() >= 2:
                out.append(c)
        else:
            if frame[c].nunique() >= 2 and frame[c].std() > 0:
                out.append(c)
    return out


def control_rhs(ctrl: list[str], frame: pd.DataFrame | None = None) -> str:
    """Contrôles catégoriels : la modalité de référence est la plus fréquente (évite une référence minuscule qui gonfle les IC)."""
    def term(c: str) -> str:
        if c not in CATEGORICAL:
            return c
        if frame is not None and c in frame.columns and frame[c].notna().any():
            ref = str(frame[c].value_counts().index[0]).replace("'", "")
            return f"C({c}, Treatment(reference='{ref}'))"
        return f"C({c})"
    return " + ".join(term(c) for c in ctrl)


def _join(*parts: str) -> str:
    return " + ".join(p for p in parts if p)


def _ncols(rhs: str, frame: pd.DataFrame) -> int:
    return len(patsy.dmatrix(rhs, frame).design_info.column_names) - 1


def fit_family(spec: dict, frame: pd.DataFrame, oc: str, forms: dict[str, str], plan: dict) -> dict[str, L.ModelFit]:
    epv_min = plan["general"]["epv_min"]
    if spec["outcome"] == "ordinal":
        return {k: L.fit_ordinal(rhs, frame, oc) for k, rhs in forms.items()}
    n = len(frame)
    events = int(frame[oc].sum())
    kmax = max(_ncols(r, frame) for r in forms.values())
    epv = min(events, n - events) / max(kmax, 1)
    method = spec["method"]
    note = None
    if method == "auto":
        if epv < epv_min:
            method = "firth"
            note = f"EPV = {epv:.1f} < {epv_min:g} pour le modèle le plus riche : régression pénalisée de Firth utilisée."
        else:
            method = "ml"
    try:
        fits = {k: L.fit_binary(f"{oc} ~ {rhs}", frame, method=method, epv_min=epv_min) for k, rhs in forms.items()}
    except RuntimeError:
        if spec["method"] == "ml":
            raise
        fits = {k: L.fit_binary(f"{oc} ~ {rhs}", frame, method="firth", epv_min=epv_min) for k, rhs in forms.items()}
        note = "Séparation détectée en maximum de vraisemblance : Firth utilisé pour toute la famille de modèles."
    if note:
        for f in fits.values():
            f.warnings.append(note)
    return fits


def find_term(names: list[str], parts: set[str]) -> str | None:
    for n in names:
        if set(n.split(":")) == parts:
            return n
    return None


def row_with_label(fit: L.ModelFit, term: str, label: str | None = None) -> dict:
    r = fit.row(term)
    r["label"] = label or pretty_term(term)
    return r


def untestable(hid: str, reason: str, n: int = 0, events: int = 0) -> dict:
    return {"id": hid, "testable": False, "reason": reason, "n": n, "events": events, "primary": None, "sign_ok": None,
            "details": [], "extra": {}}


# ------------------------------------------------------------------------------------------- estimation

def estimate(df: pd.DataFrame, plan: dict, spec: dict) -> dict:
    a = plan["general"]["alpha"]
    frame, oc, ctrl = build_frame(df, plan, spec)
    n = len(frame)
    out: dict[str, Any] = {"spec": spec, "n": n, "H": {}, "models": {}, "outcome_col": oc, "frame": frame, "warnings": []}
    if n < plan["general"]["min_n_model"] or frame[oc].nunique() < 2:
        reason = f"Effectif analysable insuffisant (n = {n} < {plan['general']['min_n_model']}) ou issue sans variation."
        for h in ("H1", "H2", "H3", "H4", "H5"):
            out["H"][h] = untestable(h, reason, n)
        return out
    events = int(frame[oc].sum()) if spec["outcome"] != "ordinal" else int((frame[oc] > 0).sum())
    ctrl = usable_controls(ctrl, frame)
    crhs = control_rhs(ctrl, frame)
    risk = "z_gouvernance + z_competences_risque + z_communication_risque + z_soutien"
    inter = "z_soutien:z_gouvernance + z_soutien:z_competences_risque + z_soutien:z_communication_risque"
    forms = {"A": _join("z_gouvernance", crhs), "B": _join(risk, crhs), "C": _join(risk, inter, crhs)}
    try:
        fits = fit_family(spec, frame, oc, forms, plan)
    except Exception as e:  # noqa: BLE001
        reason = f"Modèle non estimable ({type(e).__name__}: {e})"
        for h in ("H1", "H2", "H3", "H4", "H5"):
            out["H"][h] = untestable(h, reason, n, events)
        return out
    A, B, C = fits["A"], fits["B"], fits["C"]
    out["models"].update({"A": A, "B": B, "C": C})
    out["events"] = events
    out["k_B"] = B.k
    out["epv"] = float(min(events, n - events) / max(B.k, 1)) if spec["outcome"] != "ordinal" else float("nan")
    out["method"] = B.method

    def wald_h(hid: str, fit: L.ModelFit, term: str) -> dict:
        r = row_with_label(fit, term)
        return {"id": hid, "testable": True, "reason": None, "n": fit.nobs, "events": events,
                "primary": {"kind": "wald", **r}, "sign_ok": r["coef"] > 0,
                "details": [row_with_label(B, term, r["label"] + " — modèle complet (effet net)")] if fit is not B else [],
                "extra": {}}

    out["H"]["H1"] = wald_h("H1", A, "z_gouvernance")
    out["H"]["H2"] = wald_h("H2", B, "z_competences_risque")
    out["H"]["H5"] = wald_h("H5", B, "z_communication_risque")

    # --- H3 : interactions soutien × facteurs de risque
    lr3 = L.lr_test(C, B)
    names = C.names
    rows3 = []
    for rname, lab in (("gouvernance", "Soutien × gouvernance centralisée"), ("competences_risque", "Soutien × faibles compétences"),
                       ("communication_risque", "Soutien × faible communication")):
        t = find_term(names, {"z_soutien", f"z_{rname}"})
        if t:
            rows3.append(row_with_label(C, t, lab))
    sig_neg = any(r["p"] < a and r["coef"] < 0 for r in rows3)
    sig_pos = any(r["p"] < a and r["coef"] > 0 for r in rows3)
    sum_coef = sum(r["coef"] for r in rows3)
    sign3 = (not sig_pos) and (sig_neg or sum_coef < 0)
    out["H"]["H3"] = {
        "id": "H3", "testable": True, "reason": None, "n": n, "events": events,
        "primary": {"kind": "lr", "label": "Test conjoint des 3 interactions", **lr3},
        "sign_ok": bool(sign3), "details": rows3,
        "extra": {"individual_hit": bool(sig_neg), "individual_contradiction": bool(sig_pos)},
    }

    # --- H4 : formalisation
    out["H"]["H4"] = _h4(frame, oc, spec, plan, risk, crhs, ctrl, events)
    for k in ("Bh4", "D", "F0", "F1"):
        if k in out["H"]["H4"].get("_fits", {}):
            out["models"][k] = out["H"]["H4"]["_fits"][k]
    out["H"]["H4"].pop("_fits", None)
    return out


def _h4(frame: pd.DataFrame, oc: str, spec: dict, plan: dict, risk: str, crhs: str, ctrl: list[str], events_all: int) -> dict:
    a = plan["general"]["alpha"]
    minc = plan["formalisation"]["min_category_n"]
    f4 = frame.dropna(subset=["formalisation_cat"]).copy()
    n4 = len(f4)
    counts = f4["formalisation_cat"].value_counts().to_dict()
    if n4 < plan["general"]["min_n_model"] or len(counts) < 2 or f4[oc].nunique() < 2:
        r = untestable("H4", f"Catégories de formalisation insuffisantes (effectifs : {counts}).", n4, events_all)
        r["extra"] = {"counts": counts}
        return r
    ref = "formel" if "formel" in counts else max(counts, key=counts.get)
    ctrl_use = usable_controls(ctrl, f4)
    crhs4 = control_rhs(ctrl_use, f4)
    fcat = f"C(formalisation_cat, Treatment(reference='{ref}'))"
    forms = {"Bh4": _join(risk, fcat, crhs4), "D": _join(risk, fcat, f"z_gouvernance:{fcat}", crhs4)}
    fits = fit_family(spec, f4, oc, forms, plan)
    Bh, D = fits["Bh4"], fits["D"]
    lr = L.lr_test(D, Bh)
    # effets simples de la gouvernance par catégorie
    cov = D.cov
    main = "z_gouvernance"
    slopes = []
    base_b = float(D.params[main])
    inter_cols = {}
    for nme in D.names:
        if ":" in nme and "z_gouvernance" in nme.split(":") and "formalisation_cat" in nme:
            m = re.search(r"\[T\.(.+?)\]", nme)
            if m:
                inter_cols[m.group(1)] = nme
    for cat in sorted(counts, key=lambda c: ["informel", "semi-formel", "formel"].index(c) if c in ["informel", "semi-formel", "formel"] else 9):
        if cat == ref:
            b, var = base_b, float(cov.loc[main, main])
        else:
            col = inter_cols.get(cat)
            if col is None:
                continue
            b = base_b + float(D.params[col])
            var = float(cov.loc[main, main] + cov.loc[col, col] + 2 * cov.loc[main, col])
        se = math.sqrt(max(var, 0))
        z = b / se if se > 0 else float("nan")
        slopes.append({
            "category": cat, "n": int(counts[cat]), "coef": b, "or": math.exp(b), "ci_low": math.exp(b - 1.959964 * se),
            "ci_high": math.exp(b + 1.959964 * se), "p": float(2 * stats.norm.sf(abs(z))) if se > 0 else float("nan"),
            "small": bool(counts[cat] < minc),
        })
    order = [s for s in slopes if s["category"] in ("informel", "semi-formel", "formel")]
    monotone = all(order[i]["coef"] >= order[i + 1]["coef"] - 1e-9 for i in range(len(order) - 1)) if len(order) >= 2 else False
    # propriété familiale
    extra: dict[str, Any] = {"counts": counts, "reference": ref, "slopes": slopes, "monotone": bool(monotone)}
    f5 = frame.dropna(subset=["famille"]).copy()
    fam_row = None
    fam_slopes = []
    if len(f5) >= plan["general"]["min_n_model"] and f5["famille"].nunique() == 2 and f5[oc].nunique() >= 2:
        crhs5 = control_rhs(usable_controls(ctrl, f5), f5)
        forms5 = {"F0": _join(risk, "famille", crhs5), "F1": _join(risk, "famille", "z_gouvernance:famille", crhs5)}
        try:
            fits5 = fit_family(spec, f5, oc, forms5, plan)
            F1 = fits5["F1"]
            t = find_term(F1.names, {"z_gouvernance", "famille"})
            if t:
                fam_row = row_with_label(F1, t, "Gouvernance × propriété familiale")
                v = F1.cov
                b0 = float(F1.params["z_gouvernance"])
                b1 = b0 + float(F1.params[t])
                se0 = math.sqrt(float(v.loc["z_gouvernance", "z_gouvernance"]))
                se1 = math.sqrt(float(v.loc["z_gouvernance", "z_gouvernance"] + v.loc[t, t] + 2 * v.loc["z_gouvernance", t]))
                for lab, b, se, nn in (("Non familiale", b0, se0, int((f5["famille"] == 0).sum())), ("Familiale", b1, se1, int((f5["famille"] == 1).sum()))):
                    z = b / se if se > 0 else float("nan")
                    fam_slopes.append({"category": lab, "n": nn, "coef": b, "or": math.exp(b), "ci_low": math.exp(b - 1.959964 * se),
                                       "ci_high": math.exp(b + 1.959964 * se), "p": float(2 * stats.norm.sf(abs(z))) if se > 0 else float("nan")})
                fits["F0"], fits["F1"] = fits5["F0"], fits5["F1"]
        except Exception:  # noqa: BLE001
            fam_row = None
    extra["family_interaction"] = fam_row
    extra["family_slopes"] = fam_slopes
    # tendance linéaire (informel = 0, semi-formel = 1, formel = 2) : test directionnel plus puissant que l'omnibus à 2 ddl
    trend_row = None
    trend_lr = None
    ordmap = {"informel": 0.0, "semi-formel": 1.0, "formel": 2.0}
    f4["formal_ord"] = f4["formalisation_cat"].map(ordmap)
    if f4["formal_ord"].nunique() >= 2:
        try:
            ft = fit_family(spec, f4, oc, {"T0": _join(risk, "formal_ord", crhs4), "T1": _join(risk, "formal_ord", "z_gouvernance:formal_ord", crhs4)}, plan)
            t = find_term(ft["T1"].names, {"z_gouvernance", "formal_ord"})
            if t:
                trend_row = row_with_label(ft["T1"], t, "Gouvernance × niveau de formalisation (tendance linéaire)")
                trend_lr = L.lr_test(ft["T1"], ft["T0"])
        except Exception:  # noqa: BLE001
            trend_row = None
    extra["trend"] = trend_row
    extra["trend_lr"] = trend_lr
    sign_ok = bool(trend_row["coef"] < 0) if trend_row else bool(monotone)
    return {
        "id": "H4", "testable": True, "reason": None, "n": n4, "events": int(f4[oc].sum()) if spec["outcome"] != "ordinal" else int((f4[oc] > 0).sum()),
        "primary": {"kind": "lr", "label": "Interaction gouvernance × formalisation", **lr},
        "sign_ok": sign_ok, "details": slopes + ([fam_row] if fam_row else []), "extra": extra, "_fits": fits,
    }


# --------------------------------------------------------------------------------------------- verdicts

VERDICT_LABELS = {
    "supported": "Soutenue",
    "partial": "Partiellement soutenue",
    "not_supported": "Non soutenue",
    "contradicted": "Contredite",
    "untestable": "Non testable pour l'instant",
}


def verdict(h: dict, p_holm: float | None, alpha: float) -> tuple[str, str]:
    if not h["testable"]:
        return "untestable", h.get("reason") or VERDICT_LABELS["untestable"]
    p = h["primary"]["p"]
    sign = h["sign_ok"]
    if h["id"] == "H3":
        ex = h["extra"]
        if ex.get("individual_contradiction"):
            return "contradicted", "Contredite : au moins une interaction significative va dans le sens inverse (soutien amplifiant le risque)."
        if p < alpha and p_holm is not None and p_holm < alpha and sign:
            return "supported", "Soutenue : le soutien de la direction atténue l'effet des facteurs de risque (test conjoint significatif après correction de Holm)."
        if (p < alpha and sign) or ex.get("individual_hit"):
            return "partial", "Partiellement soutenue : effet modérateur observé mais non robuste à la correction des comparaisons multiples ou limité à une interaction."
        if p < alpha:
            return "not_supported", "Non soutenue : modération détectée mais de direction hétérogène selon les facteurs de risque (pas d'atténuation d'ensemble)."
        return "not_supported", "Non soutenue : aucune modération significative du soutien de la direction détectée."
    if h["id"] == "H4":
        ex = h["extra"]
        fam = ex.get("family_interaction")
        tr = ex.get("trend")
        fam_hit = bool(fam and fam["p"] < alpha and fam["coef"] > 0)
        trend_hit = bool(tr and tr["p"] < alpha and tr["coef"] < 0)
        if tr and tr["p"] < alpha and tr["coef"] > 0:
            return "contradicted", "Contredite : l'effet de la gouvernance augmente significativement avec la formalisation."
        if p < alpha and p_holm is not None and p_holm < alpha and sign and (ex.get("monotone") or trend_hit):
            return "supported", "Soutenue : l'effet de la gouvernance décroît avec la formalisation (interaction significative après correction de Holm)."
        if p < alpha and p_holm is not None and p_holm < alpha and sign:
            return "partial", "Partiellement soutenue : la formalisation modère bien l'effet de la gouvernance (significatif après Holm), mais le profil n'est pas décroissant de l'informel au formel."
        if (p < alpha and sign) or trend_hit or fam_hit:
            return "partial", "Partiellement soutenue : modération observée (formalisation, tendance ou gouvernance familiale) mais non robuste à la correction de Holm."
        if p < alpha:
            return "not_supported", "Non soutenue : modération détectée mais dont la direction ne correspond pas à H4 (non décroissante avec la formalisation)."
        return "not_supported", "Non soutenue : pas de modération détectable de la formalisation."
    if p < alpha and not sign:
        return "contradicted", "Contredite : effet significatif en sens inverse de l'hypothèse."
    if p_holm is not None and p_holm < alpha and sign:
        return "supported", "Soutenue : effet significatif dans le sens attendu, y compris après correction de Holm."
    if p < alpha and sign:
        return "partial", "Partiellement soutenue : significatif avant correction de Holm, non significatif après."
    if sign:
        return "not_supported", "Non soutenue : effet dans le sens attendu mais non significatif (tendance)."
    return "not_supported", "Non soutenue : aucun effet détecté."


def _p_for_text(h: dict) -> str:
    return fp(h["primary"]["p"]) if h.get("primary") else "p = —"


def interpret(h: dict, hdef: dict, vkey: str, p_holm: float | None) -> str:
    if not h["testable"]:
        return h.get("reason") or ""
    p = h["primary"]
    hid = h["id"]
    subj = {
        "H1": "de centralisation des décisions du projet",
        "H2": "de faiblesse des compétences numériques de l'équipe",
        "H5": "de faiblesse de la communication interne",
    }
    parts: list[str] = []
    if hid in subj:
        if p["or"] >= 1:
            parts.append(f"Chaque écart-type supplémentaire {subj[hid]} multiplie les chances d'échec par {fnum(p['or'])} "
                         f"(IC 95 % {fnum(p['ci_low'])}–{fnum(p['ci_high'])} ; {fp(p['p'])}).")
        else:
            parts.append(f"Chaque écart-type supplémentaire {subj[hid]} est associé à des chances d'échec réduites de {fnum(100 * (1 - p['or']), 0)} % "
                         f"(OR = {fnum(p['or'])}, IC 95 % {fnum(p['ci_low'])}–{fnum(p['ci_high'])} ; {fp(p['p'])}), soit l'inverse du sens attendu.")
    elif hid == "H3":
        parts.append(f"Le test conjoint des trois interactions soutien × facteur de risque donne χ²({p['df']}) = {fnum(p['stat'])}, {fp(p['p'])}.")
        for r in h["details"]:
            parts.append(f"{r['label']} : OR = {fnum(r['or'])} (IC 95 % {fnum(r['ci_low'])}–{fnum(r['ci_high'])} ; {fp(r['p'])}).")
        parts.append("Un OR inférieur à 1 signifie que le soutien de la direction réduit l'effet du facteur de risque.")
    elif hid == "H4":
        parts.append(f"Le test de l'interaction gouvernance × formalisation (χ²({p['df']}) = {fnum(p['stat'])}) donne {fp(p['p'])}.")
        for s in h["extra"].get("slopes", []):
            tag = " (effectif réduit, à interpréter avec prudence)" if s.get("small") else ""
            parts.append(f"Entreprises {s['category']} (n = {s['n']}) : OR de la gouvernance = {fnum(s['or'])} (IC 95 % {fnum(s['ci_low'])}–{fnum(s['ci_high'])}){tag}.")
        tr = h["extra"].get("trend")
        if tr:
            parts.append(f"Tendance linéaire (informel → formel) : OR de l'interaction = {fnum(tr['or'])} ({fp(tr['p'])}) ; "
                         + ("l'effet de la gouvernance diminue avec la formalisation." if tr["coef"] < 0 else "l'effet de la gouvernance ne diminue pas avec la formalisation."))
        fam = h["extra"].get("family_interaction")
        if fam:
            parts.append(f"Interaction gouvernance × propriété familiale : OR = {fnum(fam['or'])} ({fp(fam['p'])}).")
    if p_holm is not None:
        parts.append("p corrigé (Holm) " + ("< 0,001" if p_holm < 0.001 else "= " + fnum(p_holm, 3)) + ".")
    parts.append(f"Décision : {VERDICT_LABELS[vkey].lower()}.")
    return " ".join(parts)


# --------------------------------------------------------------------------------------------- orchestration

def _compact(h: dict) -> dict:
    p = h.get("primary")
    if not h["testable"] or not p:
        return {"testable": False, "n": h.get("n", 0)}
    return {"testable": True, "n": h["n"], "kind": p["kind"], "or": p.get("or"), "ci_low": p.get("ci_low"), "ci_high": p.get("ci_high"),
            "p": p["p"], "sign_ok": h["sign_ok"], "stat": p.get("stat"), "df": p.get("df")}


def power_block(est: dict) -> dict:
    """Plus petit OR détectable (80 % / 90 %) pour H1, H2, H5 et les interactions de H3."""
    out: dict[str, Any] = {}
    B, C = est["models"].get("B"), est["models"].get("C")
    if B is None or B.X is None or B.y is None:
        return out
    n, prev = B.nobs, float(np.mean(B.y > 0)) if est["spec"]["outcome"] != "ordinal" else float(np.mean(B.y > 0))
    X = B.X.drop(columns=["Intercept"], errors="ignore")
    for hid, term in (("H1", "z_gouvernance"), ("H2", "z_competences_risque"), ("H5", "z_communication_risque")):
        if term in X.columns:
            r2 = r2_on_others(X[term].to_numpy(float), X.drop(columns=[term]).to_numpy(float))
            obs = est["H"][hid]["primary"]["or"] if est["H"][hid].get("primary") else None
            out[hid] = {"r2_others": r2, "mde_80": min_detectable_or(n, prev, r2, power=0.8), "mde_90": min_detectable_or(n, prev, r2, power=0.9),
                        "observed_or": obs, "achieved_power": power_for_or(n, prev, obs, r2) if obs else None}
    if C is not None and C.X is not None:
        XC = C.X.drop(columns=["Intercept"], errors="ignore")
        mdes = []
        for col in XC.columns:
            if ":" in col:
                r2 = r2_on_others(XC[col].to_numpy(float), XC.drop(columns=[col]).to_numpy(float))
                mdes.append(min_detectable_or(n, prev, r2, power=0.8))
        if mdes:
            out["H3"] = {"mde_80": float(np.median(mdes)), "note": "médiane des 3 interactions"}
    out["_n"], out["_prevalence"] = n, prev
    return out


def run_hypotheses(df: pd.DataFrame, plan: dict, with_robustness: bool = True) -> dict:
    a = plan["general"]["alpha"]
    est = estimate(df, plan, SPECS[0])
    H = est["H"]
    hdefs = {h["id"]: h for h in plan["hypotheses"]}
    # correction de Holm sur la famille confirmatoire
    pvals = {hid: h["primary"]["p"] for hid, h in H.items() if h["testable"] and h["primary"] and hid in plan["models"]["holm_family"]}
    padj = holm(pvals)
    res_h = []
    for hid in ["H1", "H2", "H3", "H4", "H5"]:
        h = H[hid]
        hdef = hdefs.get(hid, {})
        vkey, vtext = verdict(h, padj.get(hid), a)
        item = {
            "id": hid, "qs": hdef.get("qs"), "os": hdef.get("os"), "statement": hdef.get("statement"), "question": hdef.get("question"),
            "objective": hdef.get("objective"), "test": hdef.get("test"), "expected": hdef.get("expected"),
            "testable": h["testable"], "reason": h.get("reason"), "n": h["n"], "events": h["events"],
            "primary": h["primary"], "p_holm": padj.get(hid), "sign_ok": h["sign_ok"],
            "details": h["details"], "extra": h["extra"], "verdict": vkey, "verdict_label": VERDICT_LABELS[vkey], "verdict_text": vtext,
            "interpretation": interpret(h, hdef, vkey, padj.get(hid)),
        }
        res_h.append(item)
    models: dict[str, Any] = {}
    if "B" in est["models"]:
        for key, title in (("A", "Modèle A — gouvernance seule + contrôles (H1)"), ("B", "Modèle B — modèle multiple (H1, H2, H5)"),
                           ("C", "Modèle C — avec interactions du soutien (H3)")):
            fit = est["models"][key]
            models[key] = {"title": title, "coefficients": L.coef_table(fit, {t: pretty_term(t) for t in fit.names}),
                           "diagnostics": L.diagnostics(fit)}
        if "D" in est["models"]:
            models["D"] = {"title": "Modèle D — gouvernance × formalisation (H4)",
                           "coefficients": L.coef_table(est["models"]["D"], {t: pretty_term(t) for t in est["models"]["D"].names}),
                           "diagnostics": L.diagnostics(est["models"]["D"])}
    robustness: dict[str, list] = {h: [] for h in ("H1", "H2", "H3", "H4", "H5")}
    if with_robustness and est["n"] >= plan["general"]["min_n_model"]:
        for sp in SPECS:
            e2 = est if sp["name"] == "Principal" else None
            if e2 is None:
                try:
                    e2 = estimate(df, plan, sp)
                except Exception as ex:  # noqa: BLE001
                    for hid in robustness:
                        robustness[hid].append({"spec": sp["name"], "desc": sp["desc"], "testable": False, "note": str(ex)})
                    continue
            for hid in robustness:
                c = _compact(e2["H"][hid])
                c.update({"spec": sp["name"], "desc": sp["desc"]})
                robustness[hid].append(c)
    # synthèse de robustesse : proportion de spécifications dans le sens attendu
    for hid, lst in robustness.items():
        ok = [r for r in lst if r.get("testable") and r.get("sign_ok")]
        tot = [r for r in lst if r.get("testable")]
        sig = [r for r in tot if r.get("p") is not None and r["p"] < a and r.get("sign_ok")]
        for item in res_h:
            if item["id"] == hid:
                item["robustness_summary"] = {"specs_tested": len(tot), "sign_ok": len(ok), "significant_expected": len(sig)}
    try:
        _add_curves(res_h, est)
    except Exception:  # noqa: BLE001  (les courbes sont un plus : ne jamais faire échouer l'analyse)
        pass
    warnings = build_warnings(est, plan)
    power = power_block(est) if "B" in est["models"] else {}
    out = {
        "n_analysable": int(df["analysable"].sum()),
        "n_model": est["n"],
        "events": est.get("events"),
        "epv": est.get("epv"),
        "method": est.get("method"),
        "target": plan["general"]["target_n"],
        "alpha": a,
        "models": models,
        "hypotheses": res_h,
        "robustness": robustness,
        "power": power,
        "warnings": warnings,
        "specs": [{"name": s["name"], "desc": s["desc"]} for s in SPECS],
    }
    return jsonable(out)


def _add_curves(res_h: list[dict], est: dict) -> None:
    from . import curves as CV
    for item in res_h:
        if item["id"] == "H3" and item["testable"] and "C" in est["models"]:
            C = est["models"]["C"]
            item["extra"] = dict(item.get("extra") or {})
            item["extra"]["curves"] = {
                "Gouvernance centralisée": CV.continuous_moderator(C, "z_gouvernance"),
                "Faibles compétences": CV.continuous_moderator(C, "z_competences_risque"),
                "Faible communication": CV.continuous_moderator(C, "z_communication_risque"),
            }
        if item["id"] == "H4" and item["testable"]:
            fits = {"D": est["models"].get("D")} if est["models"].get("D") is not None else None
            if fits and "D" in fits:
                cats = [c for c in ("informel", "semi-formel", "formel") if c in (est["H"]["H4"]["extra"].get("counts") or {})]
                item["extra"] = dict(item.get("extra") or {})
                item["extra"]["curves"] = {"Gouvernance centralisée": CV.categorical_moderator(fits["D"], "z_gouvernance", cats)}


def build_warnings(est: dict, plan: dict) -> list[dict]:
    w: list[dict] = []
    tgt = plan["general"]["target_n"]
    n = est["n"]
    if n < tgt["min"]:
        w.append({"level": "warn", "text": f"n = {n} projets analysables, sous la cible minimale du protocole ({tgt['min']}). Résultats provisoires."})
    if "B" in est["models"]:
        epv = est.get("epv")
        if epv is not None and not (isinstance(epv, float) and math.isnan(epv)) and epv < plan["general"]["epv_min"]:
            w.append({"level": "warn", "text": f"EPV = {epv:.1f} (< {plan['general']['epv_min']:g}) : trop peu d'échecs (ou de succès) pour le nombre de paramètres ; "
                                               "la régression de Firth est utilisée et il faut réduire les variables de contrôle si possible."})
        for f in est["models"].values():
            for note in f.warnings:
                if note not in [x["text"] for x in w]:
                    w.append({"level": "info", "text": note})
            break
        vif = L.vif_table(est["models"]["B"].X) if est["models"]["B"].X is not None else []
        bad = [v for v in vif if v["vif"] > 5 and not v["term"].startswith("C(")]
        if bad:
            w.append({"level": "warn", "text": "Colinéarité élevée (VIF > 5) : " + ", ".join(f"{pretty_term(v['term'])} ({fnum(v['vif'], 1)})" for v in bad)})
    h4 = est["H"].get("H4", {})
    if h4.get("testable") and any(s.get("small") for s in h4["extra"].get("slopes", [])):
        w.append({"level": "warn", "text": "Au moins une catégorie de formalisation compte moins de "
                                           f"{plan['formalisation']['min_category_n']} projets : l'effet simple correspondant est très incertain."})
    w.append({"level": "info", "text": "Échantillon non probabiliste (choix raisonné + quotas) : les résultats ne se généralisent pas à toutes les PME béninoises."})
    return w
