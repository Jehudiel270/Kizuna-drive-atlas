"""Graphes : (1) modèle conceptuel du protocole avec effets estimés ; (2) réseau exploratoire de corrélations partielles
(EBIC-glasso) avec garde-fou de stabilité (CS-coefficient). Exports GraphML / GEXF / JSON.
"""
from __future__ import annotations

import io
import math
import warnings
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.covariance import graphical_lasso

from ..core.fmt import jsonable

# ------------------------------------------------------------------------------------ modèle conceptuel

NODES = [
    {"id": "gov", "label": "Gouvernance centralisée", "tag": "VI1", "group": "predictor", "pos": [-4.2, 1.6, 0.0]},
    {"id": "comp", "label": "Faibles compétences numériques", "tag": "VI2", "group": "predictor", "pos": [-4.2, -0.2, 0.0]},
    {"id": "com", "label": "Faible communication interne", "tag": "VI3", "group": "predictor", "pos": [-4.2, -2.0, 0.0]},
    {"id": "sup", "label": "Soutien de la direction", "tag": "VI4", "group": "moderator", "pos": [-1.2, -3.9, 2.6]},
    {"id": "form", "label": "Niveau de formalisation", "tag": "Modérateur", "group": "moderator", "pos": [-2.0, 4.0, -2.6]},
    {"id": "fam", "label": "Gouvernance familiale", "tag": "Modérateur", "group": "moderator", "pos": [-2.0, 4.6, 1.6]},
    {"id": "ctrl", "label": "Contrôles : taille, secteur, ancienneté, type de projet", "tag": "Contrôles", "group": "control", "pos": [1.8, -4.4, -2.8]},
    {"id": "issue", "label": "Échec du projet de digitalisation", "tag": "Issue", "group": "outcome", "pos": [3.4, 0.0, 0.0]},
]


def conceptual_graph(hyp: dict) -> dict:
    """Construit le graphe du cadre conceptuel (protocole 3.6) à partir des résultats de `run_hypotheses`."""
    byid = {h["id"]: h for h in hyp.get("hypotheses", [])}
    modelB = hyp.get("models", {}).get("B", {}).get("coefficients", [])
    coef = {c["term"]: c for c in modelB}
    edges: list[dict[str, Any]] = []

    def edge(src, dst, kind, hid, row, label, expected):
        if not row:
            edges.append({"source": src, "target": dst, "kind": kind, "hypothesis": hid, "label": label, "or": None, "ci_low": None, "ci_high": None,
                          "p": None, "significant": None, "expected": expected, "estimated": False})
            return
        edges.append({"source": src, "target": dst, "kind": kind, "hypothesis": hid, "label": label, "or": row.get("or"), "ci_low": row.get("ci_low"),
                      "ci_high": row.get("ci_high"), "p": row.get("p"), "significant": bool(row.get("p") is not None and row["p"] < hyp.get("alpha", 0.05)),
                      "expected": expected, "estimated": True})

    h1 = byid.get("H1", {}).get("primary")
    edge("gov", "issue", "direct", "H1", h1, "H1 : gouvernance → échec", "+")
    edge("comp", "issue", "direct", "H2", coef.get("z_competences_risque"), "H2 : faibles compétences → échec", "+")
    edge("com", "issue", "direct", "H5", coef.get("z_communication_risque"), "H5 : faible communication → échec", "+")
    edge("sup", "issue", "direct", None, coef.get("z_soutien"), "Soutien de la direction → échec (effet direct)", "-")
    edge("ctrl", "issue", "direct", None, None, "Variables de contrôle", None)
    h3 = byid.get("H3", {})
    names = {"Soutien × gouvernance centralisée": "gov", "Soutien × faibles compétences": "comp", "Soutien × faible communication": "com"}
    for r in h3.get("details", []) or []:
        tgt = names.get(r.get("label"))
        if tgt:
            edge("sup", tgt, "moderation", "H3", r, f"H3 : soutien × {tgt}", "-")
    h4 = byid.get("H4", {})
    tr = (h4.get("extra") or {}).get("trend")
    edge("form", "gov", "moderation", "H4", tr, "H4 : formalisation × gouvernance (tendance)", "-")
    fam = (h4.get("extra") or {}).get("family_interaction")
    edge("fam", "gov", "moderation", "H4", fam, "H4 : gouvernance familiale × gouvernance", "+")
    return {"nodes": NODES, "edges": edges, "note": "OR par écart-type du prédicteur (modèle multiple). Les arêtes de modération sont des rapports de cotes d'interaction."}


# ------------------------------------------------------------------------------------ réseau exploratoire

def _nearest_psd(S: np.ndarray, eps: float = 1e-3) -> np.ndarray:
    w, v = np.linalg.eigh((S + S.T) / 2)
    w = np.clip(w, eps, None)
    A = (v * w) @ v.T
    d = np.sqrt(np.diag(A))
    return A / np.outer(d, d)


def _partial_from_precision(P: np.ndarray) -> np.ndarray:
    d = np.sqrt(np.diag(P))
    pc = -P / np.outer(d, d)
    np.fill_diagonal(pc, 0.0)
    return pc


def _ebic(S: np.ndarray, P: np.ndarray, n: int, gamma: float) -> float:
    p = S.shape[0]
    sign, logdet = np.linalg.slogdet(P)
    ll = n / 2 * (logdet - float(np.trace(S @ P)))
    e = int((np.abs(np.triu(P, 1)) > 1e-8).sum())
    return float(-2 * ll + e * math.log(n) + 4 * gamma * e * math.log(p))


def _fit_glasso(S: np.ndarray, alpha: float) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, P = graphical_lasso(S, alpha=alpha, max_iter=60, tol=1e-3, enet_tol=1e-3)
    return _partial_from_precision(P)


def _strength(W: np.ndarray) -> np.ndarray:
    return np.abs(W).sum(axis=1)


def explore_network(df: pd.DataFrame, plan: dict, items: dict[str, str], seed: int | None = None) -> dict:
    cfg = plan["network"]
    seed = seed if seed is not None else plan["general"]["seed"]
    rng = np.random.default_rng(seed)
    base = df[df["analysable"]]
    cols = [c for c in items if c in base.columns]
    X = base[cols].apply(pd.to_numeric, errors="coerce")
    if "echec" in base:
        X["echec"] = base["echec"]
        items = {**items, "echec": "Échec du projet (0/1)"}
        cols = cols + ["echec"]
    X = X.dropna()
    n, p = X.shape
    res: dict[str, Any] = {"available": False, "n": int(n), "p": int(p), "min_n": cfg["min_n"]}
    if not cfg.get("enabled", True):
        res["reason"] = "Module désactivé dans le plan d'analyse."
        return jsonable(res)
    if n < cfg["min_n"]:
        res["reason"] = f"Effectif complet insuffisant (n = {n} < {cfg['min_n']}) : un réseau de {p} nœuds serait instable. Module verrouillé."
        res["status"] = "verrouille"
        return jsonable(res)
    S = _nearest_psd(X.corr(method="spearman").to_numpy())
    alphas = np.logspace(-2.2, -0.2, 30)
    best = None
    for a in alphas:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _, P = graphical_lasso(S, alpha=float(a), max_iter=200, tol=1e-4)
        except Exception:
            continue
        e = _ebic(S, P, n, cfg["ebic_gamma"])
        if best is None or e < best[0]:
            best = (e, float(a), P)
    if best is None:
        res["reason"] = "Estimation impossible."
        res["status"] = "verrouille"
        return jsonable(res)
    _, alpha_star, P = best
    W = _partial_from_precision(P)
    W[np.abs(W) < 1e-8] = 0.0
    # --- stabilité : bootstrap des arêtes et CS-coefficient (suppression de cas)
    B_edges = cfg["bootstrap"]["edges"]
    iu = np.triu_indices(p, 1)
    boots = np.zeros((B_edges, len(iu[0])))
    Xv = X.to_numpy(float)
    for b in range(B_edges):
        idx = rng.integers(0, n, n)
        Sb = _nearest_psd(pd.DataFrame(Xv[idx]).corr(method="spearman").to_numpy())
        try:
            boots[b] = _fit_glasso(Sb, alpha_star)[iu]
        except Exception:
            boots[b] = 0.0
    incl = (np.abs(boots) > 1e-8).mean(axis=0)
    lo_ci, hi_ci = np.percentile(boots, 2.5, axis=0), np.percentile(boots, 97.5, axis=0)
    str_full = _strength(W)
    cs = 0.0
    levels = []
    for drop in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        keep = max(int(round(n * (1 - drop))), p + 2)
        cors = []
        for _ in range(cfg["bootstrap"]["case_drop"]):
            idx = rng.choice(n, keep, replace=False)
            Sb = _nearest_psd(pd.DataFrame(Xv[idx]).corr(method="spearman").to_numpy())
            try:
                Wb = _fit_glasso(Sb, alpha_star)
                c = np.corrcoef(_strength(Wb), str_full)[0, 1] if np.std(_strength(Wb)) > 0 and np.std(str_full) > 0 else 0.0
            except Exception:
                c = 0.0
            cors.append(c)
        frac = float((np.array(cors) > 0.7).mean())
        levels.append({"drop": drop, "share_ok": frac, "median_corr": float(np.median(cors))})
        if frac >= 0.95:
            cs = drop
        elif frac < 0.5 and len(levels) >= 2 and levels[-2]["share_ok"] < 0.95:
            break  # le CS-coefficient est déjà déterminé : inutile de continuer
    status = "interpretable" if cs >= cfg["cs_good"] else ("exploratoire" if cs >= cfg["cs_min"] else "verrouille")
    # --- centralités, communautés, positions 3D
    G = nx.Graph()
    for i, c in enumerate(cols):
        G.add_node(c)
    for k, (i, j) in enumerate(zip(*iu)):
        if abs(W[i, j]) > 1e-8:
            G.add_edge(cols[i], cols[j], weight=float(W[i, j]), absw=float(abs(W[i, j])), inclusion=float(incl[k]),
                       ci_low=float(lo_ci[k]), ci_high=float(hi_ci[k]))
    H = nx.Graph()
    for u, v, d in G.edges(data=True):
        H.add_edge(u, v, weight=d["absw"], dist=1 / d["absw"])
    H.add_nodes_from(cols)
    closeness = nx.closeness_centrality(H, distance="dist") if H.number_of_edges() else {c: 0.0 for c in cols}
    between = nx.betweenness_centrality(H, weight="dist") if H.number_of_edges() else {c: 0.0 for c in cols}
    if H.number_of_edges():
        comms = nx.community.louvain_communities(H, weight="weight", seed=seed)
    else:
        comms = [{c} for c in cols]
    comm_of = {}
    for k, cset in enumerate(sorted(comms, key=lambda s: -len(s))):
        for c in cset:
            comm_of[c] = k
    pos = _community_layout(cols, comm_of, str_full, seed)
    ei = {cols[i]: float(W[i].sum()) for i in range(p)}
    constr = {}
    for cname, c in plan["constructs"].items():
        for it in c["items"]:
            constr[it] = cname
    nodes = []
    for i, c in enumerate(cols):
        x, y, z = pos[c]
        nodes.append({"id": c, "label": items.get(c, c), "construct": constr.get(c, "issue" if c == "echec" else "contexte"), "community": comm_of.get(c, 0),
                      "strength": float(str_full[i]), "closeness": float(closeness.get(c, 0.0)), "betweenness": float(between.get(c, 0.0)),
                      "expected_influence": ei[c], "x": float(x), "y": float(y), "z": float(z)})
    edges = [{"source": u, "target": v, "weight": d["weight"], "abs": d["absw"], "inclusion": d["inclusion"], "ci_low": d["ci_low"], "ci_high": d["ci_high"]}
             for u, v, d in G.edges(data=True)]
    res.update({"available": True, "status": status, "alpha": alpha_star, "ebic_gamma": cfg["ebic_gamma"], "nodes": nodes, "edges": edges,
                "stability": {"cs_strength": cs, "levels": levels, "cs_min": cfg["cs_min"], "cs_good": cfg["cs_good"]},
                "n_edges": len(edges), "density": len(edges) / (p * (p - 1) / 2),
                "note": "Réseau exploratoire : corrélations partielles de Spearman régularisées (EBIC-glasso). Il ne teste aucune hypothèse du protocole."})
    return jsonable(res)


def _fib_sphere(n: int, radius: float = 1.0) -> np.ndarray:
    if n == 1:
        return np.zeros((1, 3))
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    return radius * np.column_stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)])


def _community_layout(cols: list[str], comm_of: dict[str, int], strength: np.ndarray, seed: int) -> dict[str, np.ndarray]:
    """Disposition lisible en 3D : chaque communauté est un amas sur une sphère externe, les nœuds de l'amas sont répartis régulièrement ;
    la variable d'issue (échec), si présente, est placée au centre. Déterministe (pas de chevauchement de nœuds)."""
    groups: dict[int, list[str]] = {}
    for c in cols:
        if c != "echec":
            groups.setdefault(comm_of.get(c, 0), []).append(c)
    pos: dict[str, np.ndarray] = {}
    centers = _fib_sphere(len(groups), 4.6) if len(groups) > 1 else np.zeros((1, 3))
    for (gid, members), ctr in zip(sorted(groups.items()), centers):
        pts = _fib_sphere(len(members), 0.9 + 0.35 * len(members) ** 0.5)
        for m, q in zip(sorted(members, key=lambda c: -strength[cols.index(c)]), pts):
            pos[m] = ctr + q
    if "echec" in cols:
        pos["echec"] = np.zeros(3)
    return pos


# ------------------------------------------------------------------------------------ exports

def to_networkx(graph: dict) -> nx.Graph:
    G = nx.Graph()
    for n in graph.get("nodes", []):
        attrs = {k: v for k, v in n.items() if k != "id" and v is not None}
        if "pos" in attrs:
            attrs["x"], attrs["y"], attrs["z"] = attrs.pop("pos")
        G.add_node(n["id"], **attrs)
    for e in graph.get("edges", []):
        attrs = {k: v for k, v in e.items() if k not in ("source", "target") and v is not None}
        G.add_edge(e["source"], e["target"], **attrs)
    return G


def export_graph(graph: dict, fmt: str) -> tuple[bytes, str, str]:
    G = to_networkx(graph)
    if fmt == "graphml":
        buf = io.BytesIO()
        nx.write_graphml(G, buf)
        return buf.getvalue(), "application/graphml+xml", "graphml"
    if fmt == "gexf":
        buf = io.BytesIO()
        nx.write_gexf(G, buf)
        return buf.getvalue(), "application/gexf+xml", "gexf"
    if fmt == "csv-edges":
        df = pd.DataFrame([{k: v for k, v in e.items()} for e in graph.get("edges", [])])
        return df.to_csv(index=False).encode("utf-8"), "text/csv", "edges.csv"
    if fmt == "csv-nodes":
        df = pd.DataFrame(graph.get("nodes", []))
        if "pos" in df:
            df = df.drop(columns=["pos"])
        return df.to_csv(index=False).encode("utf-8"), "text/csv", "nodes.csv"
    import json
    return json.dumps(graph, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", "json"
