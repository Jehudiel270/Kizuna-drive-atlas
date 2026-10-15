"""Génération du rapport d'analyse (Markdown, DOCX, XLSX) et du paquet de reproductibilité (ZIP) à partir des résultats mis en cache."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone

import pandas as pd
import yaml

from . import analysis as A
from .core.fmt import fnum, fp
from .service import Source, dataset_sha
from .stats import network as N

VERDICT_ORDER = {"supported": "Soutenue", "partial": "Partiellement soutenue", "not_supported": "Non soutenue", "contradicted": "Contredite", "untestable": "Non testable"}


def _f(v, d=2):
    return "—" if v is None else fnum(v, d)


def _or(row):
    if not row:
        return "—"
    return f"{_f(row.get('or'))} [{_f(row.get('ci_low'))} ; {_f(row.get('ci_high'))}]"


def blocks(src: Source, quali: dict | None = None) -> list[tuple]:
    """Représentation neutre du rapport : liste de blocs (type, contenu)."""
    c, h, rel, desc = A.collecte(src), A.hypotheses(src), A.fiabilite(src), A.descriptif(src)
    b: list[tuple] = []
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    b += [("title", "KIZUNA DRIVE — Rapport d'analyse des données collectées"),
          ("p", f"Généré le {now}. Source : {'instantané « ' + src.meta.get('name', '') + ' »' if src.kind == 'snapshot' else ('jeu de DÉMONSTRATION simulé' if src.kind == 'demo' else 'données courantes')}. "
                f"Empreinte du plan d'analyse : {src.plan_hash[:12]}.")]
    if src.kind == "demo":
        b.append(("callout", "ATTENTION : ces résultats proviennent de données simulées. Ils ne disent rien sur la réalité des PME béninoises."))
    b.append(("h1", "1. Données collectées"))
    b.append(("p", f"{c['n_total']} soumissions reçues, {c['n_analysable']} projets analysables (cible du protocole : {c['target']['min']}–{c['target']['max']}). "
                   f"{c['n_model']} observations complètes entrent dans les modèles."))
    b.append(("table", ["Étape", "n"], [[f["step"], f["n"]] for f in c["funnel"]]))
    b.append(("table", ["Issue du projet", "n", "%"], [[r["value"], r["n"], f"{r['pct']:.0%}"] for r in c["issue"]]))
    if c["alerts"]:
        b.append(("bullets", [a["text"] for a in c["alerts"]]))
    b.append(("h1", "2. Fiabilité des échelles"))
    b.append(("table", ["Échelle", "n", "Items", "α de Cronbach [IC 95 %]", "ω", "Statut"],
              [[r["label"], r["n"], r["k"], "—" if r["alpha"] is None else f"{_f(r['alpha'])} [{_f(r['alpha_ci'][0])} ; {_f(r['alpha_ci'][1])}]", _f(r["omega"]),
                "conforme" if r["status"] == "ok" else ("sous le seuil" if r["status"] == "faible" else "non calculable")] for r in rel]))
    b.append(("h1", "3. Descriptif par issue du projet"))
    b.append(("table", ["Variable", "Succès", "Échec partiel", "Échec total", "ANOVA p", "Kruskal p", "η²"],
              [[s["title"]] + [_f(g["mean"]) for g in s["groups"]] + [fp(s["anova"]["p"]) if s["anova"] else "—", fp(s["kruskal"]["p"]) if s["kruskal"] else "—",
                                                                      _f(s["anova"]["eta2"]) if s["anova"] else "—"] for s in desc["scores"]]))
    b.append(("h1", "4. Tests des hypothèses (protocole, section 5)"))
    b.append(("p", f"Modèle principal : régression logistique de l'échec (échec partiel + échec total) vs succès, n = {h['n_model']}, {h['events']} échecs, EPV = {_f(h['epv'], 1)}, "
                   f"méthode : {h['method']}. Seuil α = {h['alpha']} ; correction de Holm sur les 5 tests principaux. Les rapports de cotes (OR) sont donnés par écart-type du prédicteur."))
    for x in h["hypotheses"]:
        b.append(("h2", f"{x['id']} ({x['qs']} / {x['os']}) — {VERDICT_ORDER.get(x['verdict'], x['verdict'])}"))
        b.append(("p", x["statement"]))
        b.append(("p", f"Test : {x['test']}"))
        pr = x["primary"]
        if x["testable"] and pr:
            b.append(("table", ["Estimation principale", "OR [IC 95 %]", "p", "p ajusté (Holm)", "n"],
                      [[pr.get("label", x["id"]), _or(pr), fp(pr.get("p")), fp(x["p_holm"]) if x["p_holm"] is not None else "—", x["n"]]]))
        b.append(("p", x["interpretation"]))
        rs = x.get("robustness_summary")
        if rs:
            b.append(("p", f"Robustesse : {rs['sign_ok']}/{rs['specs_tested']} spécifications dans le sens attendu, {rs['significant_expected']} significatives."))
    b.append(("h2", "Puissance"))
    pw = h.get("power") or {}
    rows = [[k, _f(v.get("mde_80")), _f(v.get("mde_90")), _f(v.get("observed_or"))] for k, v in pw.items() if not k.startswith("_") and isinstance(v, dict)]
    if rows:
        b.append(("table", ["Hypothèse", "OR minimal détectable (80 %)", "(90 %)", "OR observé"], rows))
    b.append(("h1", "5. Analyse qualitative"))
    if quali and quali.get("themes"):
        b.append(("table", ["Thème", "Échecs (n)", "Succès (n)", "% échecs", "% succès", "p Fisher"],
                  [[t["theme"]["name"], t["n_echec"], t["n_succes"], f"{t['pct_echec']:.0%}" if t["pct_echec"] is not None else "—",
                    f"{t['pct_succes']:.0%}" if t["pct_succes"] is not None else "—", fp(t["p_fisher"])] for t in quali["themes"]]))
    else:
        b.append(("p", "Aucun codage thématique enregistré à ce stade."))
    kw = A.keyness(src)
    if kw.get("group_a"):
        b.append(("p", "Termes les plus caractéristiques des échecs : " + ", ".join(r["term"] for r in kw["group_a"][:8]) + ". Des succès : " + ", ".join(r["term"] for r in kw["group_b"][:8]) + "."))
    b.append(("h1", "6. Limites"))
    lim = [w["text"] for w in h["warnings"]]
    lim += src.plan.get("meta", {}).get("limits", []) or []
    b.append(("bullets", lim))
    b.append(("h1", "Annexe — reproductibilité"))
    b.append(("p", f"Empreinte du jeu de données (SHA-256) : {dataset_sha([{'id': r['_id']} for r in src.raw.to_dict('records')])[:16]}… ; plan : {src.plan_hash}. Graine aléatoire : {src.plan['general']['seed']}."))
    return b


def to_markdown(bl: list[tuple]) -> str:
    out: list[str] = []
    for t, *rest in bl:
        if t == "title":
            out.append(f"# {rest[0]}\n")
        elif t == "h1":
            out.append(f"\n## {rest[0]}\n")
        elif t == "h2":
            out.append(f"\n### {rest[0]}\n")
        elif t in ("p",):
            out.append(f"{rest[0]}\n")
        elif t == "callout":
            out.append(f"> **{rest[0]}**\n")
        elif t == "bullets":
            out.append("\n".join(f"- {x}" for x in rest[0]) + "\n")
        elif t == "table":
            head, rows = rest
            out.append("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
            out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
            out.append("")
    return "\n".join(out)


def to_docx(bl: list[tuple]) -> bytes:
    from docx import Document
    from docx.shared import Pt
    d = Document()
    d.styles["Normal"].font.name = "Calibri"
    d.styles["Normal"].font.size = Pt(10.5)
    for t, *rest in bl:
        if t == "title":
            d.add_heading(rest[0], 0)
        elif t == "h1":
            d.add_heading(rest[0], 1)
        elif t == "h2":
            d.add_heading(rest[0], 2)
        elif t == "p":
            d.add_paragraph(rest[0])
        elif t == "callout":
            p = d.add_paragraph()
            p.add_run(rest[0]).bold = True
        elif t == "bullets":
            for x in rest[0]:
                d.add_paragraph(x, style="List Bullet")
        elif t == "table":
            head, rows = rest
            tb = d.add_table(rows=1, cols=len(head))
            tb.style = "Light Grid Accent 1"
            for i, hd in enumerate(head):
                tb.rows[0].cells[i].text = str(hd)
            for r in rows:
                cells = tb.add_row().cells
                for i, v in enumerate(r):
                    cells[i].text = str(v)
            d.add_paragraph()
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def to_xlsx(src: Source) -> bytes:
    h, c, rel = A.hypotheses(src), A.collecte(src), A.fiabilite(src)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame([{"Hypothèse": x["id"], "Verdict": x["verdict_label"], "OR": (x["primary"] or {}).get("or"), "IC bas": (x["primary"] or {}).get("ci_low"),
                       "IC haut": (x["primary"] or {}).get("ci_high"), "p": (x["primary"] or {}).get("p"), "p Holm": x["p_holm"], "n": x["n"]}
                      for x in h["hypotheses"]]).to_excel(xw, sheet_name="Hypothèses", index=False)
        for k, m in h["models"].items():
            pd.DataFrame(m["coefficients"]).to_excel(xw, sheet_name=f"Modèle {k}"[:31], index=False)
        rows = [dict(hid=hid, **r) for hid, lst in h["robustness"].items() for r in lst]
        if rows:
            pd.DataFrame(rows).drop(columns=[k for k in ("details",) if rows and k in rows[0]], errors="ignore").to_excel(xw, sheet_name="Robustesse", index=False)
        pd.DataFrame([{k: v for k, v in r.items() if k not in ("items", "alpha_ci")} for r in rel]).to_excel(xw, sheet_name="Fiabilité", index=False)
        pd.DataFrame(c["funnel"]).to_excel(xw, sheet_name="Entonnoir", index=False)
    return buf.getvalue()


def analysis_frame(src: Source) -> pd.DataFrame:
    """Jeu analysable pseudonymisé (sans e-mail ni texte libre) pour le paquet de reproductibilité."""
    df = src.df[src.df["analysable"]].copy()
    drop = [c for c in ("email", "txt_facteur", "txt_autre", "enqueteur", "role_other", "secteur_other", "_respondent") if c in df]
    df = df.drop(columns=drop)
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, (list, dict))).any():
            df[col] = df[col].map(lambda v: "; ".join(map(str, v)) if isinstance(v, list) else v)
    return df


def package_zip(src: Source, quali: dict | None = None) -> bytes:
    bl = blocks(src, quali)
    h = A.hypotheses(src)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("rapport.md", to_markdown(bl))
        z.writestr("rapport.docx", to_docx(bl))
        z.writestr("tableaux.xlsx", to_xlsx(src))
        z.writestr("resultats_hypotheses.json", json.dumps(h, ensure_ascii=False, indent=2, default=str))
        z.writestr("donnees_analysables_pseudonymisees.csv", analysis_frame(src).to_csv(index=False))
        z.writestr("plan_analyse.yaml", yaml.safe_dump(src.plan, allow_unicode=True, sort_keys=False))
        z.writestr("codebook.yaml", yaml.safe_dump(src.codebook, allow_unicode=True, sort_keys=False))
        g = A.graph_model(src)
        for fmt in ("graphml", "gexf"):
            data, _, ext = N.export_graph(g, fmt)
            z.writestr(f"graphe_modele.{ext}", data)
        net = A.graph_network(src)
        if net.get("nodes"):
            z.writestr("reseau_exploratoire_aretes.csv", N.export_graph(net, "csv-edges")[0])
            z.writestr("reseau_exploratoire_noeuds.csv", N.export_graph(net, "csv-nodes")[0])
        z.writestr("LISEZMOI.txt", "Paquet de reproductibilité KIZUNA DRIVE.\n"
                   f"Empreinte du plan : {src.plan_hash}\nGraine : {src.plan['general']['seed']}\n"
                   "Pour rejouer : charger donnees_* dans l'outil (import CSV Tally), appliquer plan_analyse.yaml et codebook.yaml.\n"
                   "Les e-mails et textes libres ne sont pas inclus (pseudonymisation).\n")
    return buf.getvalue()
