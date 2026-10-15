from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from .. import analysis as A
from ..service import Source
from ..stats import descriptives as D
from ..stats import network as N
from .deps import get_source

router = APIRouter(prefix="/analysis", tags=["analyse"])


@router.get("/overview")
def overview(src: Source = Depends(get_source)):
    return A.overview(src)


@router.get("/collecte")
def collecte(src: Source = Depends(get_source)):
    return A.collecte(src)


@router.get("/coverage")
def coverage(src: Source = Depends(get_source)):
    return A.coverage(src)


@router.get("/descriptif")
def descriptif(src: Source = Depends(get_source)):
    return A.descriptif(src)


@router.get("/crosstabs")
def crosstabs(src: Source = Depends(get_source)):
    return A.crosstabs(src)


@router.get("/crosstab")
def crosstab(var: str = Query(...), src: Source = Depends(get_source)):
    if var not in D.CAT_VARS:
        raise HTTPException(400, "Variable non prévue")
    return A.crosstab(src, var)


@router.get("/fiabilite")
def fiabilite(src: Source = Depends(get_source)):
    return A.fiabilite(src)


@router.get("/hypotheses")
def hypotheses(src: Source = Depends(get_source)):
    return A.hypotheses(src)


@router.get("/hypotheses/{hid}")
def hypothesis(hid: str, src: Source = Depends(get_source)):
    res = A.hypotheses(src)
    h = next((x for x in res["hypotheses"] if x["id"] == hid.upper()), None)
    if h is None:
        raise HTTPException(404, "Hypothèse inconnue")
    return {"hypothesis": h, "robustness": res["robustness"].get(h["id"], []), "power": res["power"].get(h["id"]), "models": res["models"],
            "warnings": res["warnings"], "n_model": res["n_model"], "events": res["events"], "epv": res["epv"], "method": res["method"], "alpha": res["alpha"]}


@router.get("/modeles")
def modeles(src: Source = Depends(get_source)):
    res = A.hypotheses(src)
    return {"models": res["models"], "n_model": res["n_model"], "events": res["events"], "epv": res["epv"], "method": res["method"],
            "warnings": res["warnings"], "specs": res["specs"], "robustness": res["robustness"]}


@router.get("/puissance")
def puissance(src: Source = Depends(get_source)):
    res = A.hypotheses(src)
    return {"power": res["power"], "target": res["target"], "n_model": res["n_model"]}


@router.get("/graph/modele")
def graph_model(src: Source = Depends(get_source)):
    return A.graph_model(src)


@router.get("/graph/exploratoire")
def graph_network(src: Source = Depends(get_source)):
    return A.graph_network(src)


@router.get("/graph/export")
def graph_export(kind: str = Query("modele", pattern="^(modele|exploratoire)$"), fmt: str = Query("graphml", pattern="^(graphml|gexf|json|csv-edges|csv-nodes)$"),
                 src: Source = Depends(get_source)):
    g = A.graph_model(src) if kind == "modele" else A.graph_network(src)
    if not g.get("nodes"):
        raise HTTPException(409, g.get("reason") or "Graphe indisponible")
    data, mime, ext = N.export_graph(g, fmt)
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="kizuna-{kind}.{ext}"'})


@router.get("/keyness")
def keyness(src: Source = Depends(get_source)):
    return A.keyness(src)
