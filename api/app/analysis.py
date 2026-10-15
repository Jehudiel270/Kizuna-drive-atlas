"""Fonctions d'analyse mises en cache par jeu de données (utilisées par les routes et le rapport)."""
from __future__ import annotations

from typing import Any

from .core.plan import stable_hash
from .service import Source, cached
from .stats import collecte as COL
from .stats import descriptives as D
from .stats import hypotheses as H
from .stats import network as N
from .stats import reliability as R
from .stats import textmining as T

NET_ITEMS = ["gov_unique", "gov_consult", "gov_discute", "gov_impose", "comp_dirigeants", "comp_utilisateurs", "com_info", "com_points", "com_alerte",
             "dir_suivi", "dir_moyens", "dir_blocages", "dir_priorite", "env_adequation", "env_simplicite", "env_coupures", "env_pression"]


def collecte(src: Source) -> dict:
    return cached(src, "collecte", lambda: COL.collecte_summary(src.df, src.plan))


def hypotheses(src: Source) -> dict:
    return cached(src, "hypotheses", lambda: H.run_hypotheses(src.df, src.plan, with_robustness=True))


def descriptif(src: Source) -> dict:
    def f():
        return {"profile": D.profile(src.df), "likert": D.likert_items(src.df, src.plan, src.labels), "scores": D.scores_by_issue(src.df)}
    return cached(src, "descriptif", f)


def crosstabs(src: Source) -> list[dict]:
    return cached(src, "crosstabs", lambda: D.all_crosstabs(src.df))


def crosstab(src: Source, var: str) -> dict:
    return cached(src, "crosstab", lambda: D.crosstab_test(src.df, var), var)


def fiabilite(src: Source) -> list[dict]:
    return cached(src, "fiabilite", lambda: R.construct_reliability(src.df, src.plan, src.labels))


def graph_model(src: Source) -> dict:
    return cached(src, "graph_model", lambda: N.conceptual_graph(hypotheses(src)))


def graph_network(src: Source) -> dict:
    items = {k: src.labels.get(k, k) for k in NET_ITEMS}
    return cached(src, "graph_network", lambda: N.explore_network(src.df, src.plan, items))


def keyness(src: Source) -> dict:
    def f():
        docs = T.open_answers(src.df)
        a = [d["text"] for d in docs if d["issue"] in ("echec_partiel", "echec_total")]
        b = [d["text"] for d in docs if d["issue"] == "succes"]
        res = T.keyness(a, b, min_df=2)
        for side in ("group_a", "group_b"):
            for r in res[side]:
                src_docs = a if side == "group_a" else b
                ex = next((T.kwic(t, r["term"]) for t in src_docs if T.kwic(t, r["term"])), None)
                r["example"] = ex
        res["n_echec"], res["n_succes"] = len(a), len(b)
        return res
    return cached(src, "keyness", f)


def coverage(src: Source) -> dict:
    """Pour chaque variable du codebook : part de soumissions renseignées → vérifie que la connexion Tally alimente bien tout le questionnaire."""
    raw = src.raw
    n = len(raw)
    rows = []
    for v in src.codebook["variables"]:
        name = v["name"]
        if name == "email":
            filled = int(raw[name].notna().sum()) if name in raw else 0
        else:
            filled = int(raw[name].map(lambda x: x is not None and x == x and x != "" and x != []).sum()) if name in raw else 0
        rows.append({"name": name, "section": v.get("section"), "label": v["label"], "type": v["type"], "filled": filled, "pct": filled / n if n else 0.0,
                     "mapped": name in raw.columns})
    return {"n": n, "variables": rows, "never_seen": [r["name"] for r in rows if not r["mapped"]]}


def overview(src: Source) -> dict:
    c = collecte(src)
    h = hypotheses(src)
    return {
        "source": {"kind": src.kind, "snapshot_id": src.snapshot_id, "meta": src.meta, "plan_hash": src.plan_hash[:12]},
        "target": c["target"], "n_total": c["n_total"], "n_analysable": c["n_analysable"], "n_model": c["n_model"],
        "progress_min": c["progress_min"], "issue": c["issue"], "funnel": c["funnel"], "alerts": c["alerts"] + h["warnings"],
        "hypotheses": [{"id": x["id"], "qs": x["qs"], "os": x["os"], "statement": x["statement"], "verdict": x["verdict"], "verdict_label": x["verdict_label"],
                        "primary": x["primary"], "p_holm": x["p_holm"], "n": x["n"]} for x in h["hypotheses"]],
        "epv": h["epv"], "method": h["method"], "events": h["events"],
    }
