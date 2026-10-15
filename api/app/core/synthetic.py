"""Générateur de données SIMULÉES à structure connue.

Sert à (1) tester le moteur d'analyse (les effets plantés doivent être retrouvés), (2) alimenter la démo publique
avant la collecte réelle. Aucune donnée réelle n'est utilisée. Les effets plantés NE préjugent PAS des résultats de l'enquête.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_EFFECTS = {
    "b0": 0.0,
    "gov": 0.7,          # centralisation -> échec (H1)
    "comp": 0.6,         # faibles compétences -> échec (H2)
    "com": 0.5,          # faible communication -> échec (H5)
    "sup": -0.3,         # soutien de la direction : effet direct
    "sup_x_gov": -0.45,  # le soutien atténue l'effet de la centralisation (H3)
    "form_x_gov": -0.35, # la formalisation atténue l'effet de la centralisation (H4)
}
NULL_EFFECTS = {k: 0.0 for k in DEFAULT_EFFECTS}

RELAIS = ["Chambre consulaire A", "Chambre consulaire B", "Association PME C", "Incubateur D", "Association PME E", "Bouche-à-oreille"]
ENQUETEURS = ["Enquêteur 1", "Enquêteur 2", "Enquêteur 3"]
VILLES = ["Cotonou", "Porto-Novo", "Abomey-Calavi", "Parakou", "Autre"]
SECTEURS = ["Commerce", "Services", "Industrie", "Agroalimentaire", "Transport / Livraison", "Bâtiment / Construction (BTP)", "Santé",
            "Éducation / Formation", "Hôtellerie / Restauration / Tourisme", "Informatique / Numérique", "Autre"]
TAILLES = ["Moins de 10 employés", "De 10 à 49 employés", "De 50 à 199 employés", "200 employés ou plus"]
PAPIERS = ["Un numéro IFU (identifiant fiscal unique)", "Une inscription au registre du commerce (RCCM)", "Le statut d'« entreprenant »",
           "Les employés déclarés à la sécurité sociale (CNSS)", "Un compte bancaire professionnel (au nom de l'entreprise)"]
USAGE_SUCCES = "Il fonctionne et il est utilisé régulièrement, comme prévu"
USAGE_PARTIEL = "Il fonctionne, mais seulement une partie des personnes l'utilise (ou moins que prévu)"
USAGE_TOTAL = "On ne l'utilise presque plus, ou le projet a été abandonné"
USAGE_COURS = "Le projet est encore en cours : c'est trop tôt pour juger"
TAUX = ["0 à 24 %", "25 à 49 %", "50 à 74 %", "75 à 100 %"]

TXT_ECHEC = [
    "Le patron décidait seul et l'équipe n'était pas consultée, puis plus personne ne savait utiliser le logiciel.",
    "Le manque de formation du personnel et les coupures d'électricité ont fait abandonner l'outil.",
    "Les informations ne circulaient pas entre les employés et le patron n'a pas suivi le projet.",
    "Le prestataire a été choisi par la famille sans demander l'avis de l'équipe, l'outil ne correspondait pas à nos besoins.",
    "Pas assez d'argent pour continuer et personne n'avait les compétences en informatique.",
]
TXT_SUCCES = [
    "L'implication du patron et la formation de toute l'équipe ont fait la différence.",
    "Nous avons fait des réunions de suivi chaque semaine et chacun pouvait donner son avis sur l'outil.",
    "Un prestataire sérieux, un outil simple à utiliser et un patron qui a donné les moyens nécessaires.",
    "La communication dans l'équipe était bonne et les employés étaient habitués au numérique.",
    "Le projet a été porté par le patron qui a clairement montré que c'était une priorité.",
]


def _likert(rng: np.random.Generator, latent: np.ndarray, loading: float = 0.9, noise: float = 0.75, center: float = 3.0, sign: int = 1) -> np.ndarray:
    v = center + sign * loading * latent + rng.normal(0, noise, size=len(latent))
    return np.clip(np.rint(v), 1, 5).astype(int)


def generate(n: int = 165, seed: int = 7, effects: dict | None = None, extra_rate: float = 0.12) -> pd.DataFrame:
    """Retourne un DataFrame « brut normalisé » (mêmes colonnes que la normalisation des soumissions Tally).

    n : nombre de projets analysables visés ; des lignes inéligibles (refus, non déclarées, sans projet, en cours) sont ajoutées.
    """
    eff = {**DEFAULT_EFFECTS, **(effects or {})}
    rng = np.random.default_rng(seed)
    n_extra = int(round(n * extra_rate))
    N = n + n_extra
    # traits latents corrélés
    cov = np.array([[1, -0.25, -0.30, -0.15], [-0.25, 1, 0.30, 0.25], [-0.30, 0.30, 1, 0.25], [-0.15, 0.25, 0.25, 1]])
    L = np.linalg.cholesky(cov)
    Z = rng.normal(size=(N, 4)) @ L.T
    gov, comp, com, sup = Z[:, 0], Z[:, 1], Z[:, 2], Z[:, 3]
    F = 0.4 * comp + rng.normal(0, 0.92, N)               # formalisation latente
    famille = (rng.random(N) < 1 / (1 + np.exp(1.0 * F - 0.2))).astype(int)  # plus de gouvernance familiale si peu formalisé
    z = lambda a: (a - a.mean()) / a.std()
    logit = (eff["b0"] + eff["gov"] * z(gov) - eff["comp"] * z(comp) - eff["com"] * z(com) + eff["sup"] * z(sup)
             + eff["sup_x_gov"] * z(sup) * z(gov) + eff["form_x_gov"] * z(F) * z(gov))
    p_fail = 1 / (1 + np.exp(-logit))
    fail = rng.random(N) < p_fail
    # échec total plus probable quand le « risque » est élevé
    p_total = 1 / (1 + np.exp(-(0.4 * (z(gov) - z(comp) - z(com)) / 3)))
    total = fail & (rng.random(N) < np.clip(p_total * 0.9, 0.15, 0.85))

    rows: list[dict[str, Any]] = []
    t0 = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)
    relais_p = np.array([0.30, 0.18, 0.16, 0.14, 0.12, 0.10])
    for i in range(N):
        kind = "ok"
        if i >= n:
            kind = rng.choice(["refus", "non_declaree", "sans_projet", "en_cours"], p=[0.15, 0.25, 0.30, 0.30])
        mode = rng.choice(["En ligne (auto-administré)", "Téléphone (saisie par un enquêteur)", "Visite en personne (saisie par un enquêteur)"], p=[0.55, 0.25, 0.20])
        r: dict[str, Any] = {
            "_id": f"SIM{i + 1:04d}", "_respondent": f"RSIM{i + 1:04d}",
            "_submitted_at": t0 + timedelta(hours=float(rng.uniform(0, 24 * 42))), "_completed": True,
            "consent": "Non, je ne souhaite pas participer" if kind == "refus" else "Oui, j'accepte de participer",
            "mode": mode,
            "enqueteur": rng.choice(ENQUETEURS) if not mode.startswith("En ligne") else None,
            "relais": rng.choice(RELAIS, p=relais_p),
            "declared": "Non" if kind == "non_declaree" else "Oui",
            "taille": rng.choice(TAILLES, p=[0.55, 0.32, 0.10, 0.03]),
            "has_project": "Non" if kind == "sans_projet" else "Oui",
        }
        if kind in ("refus", "non_declaree", "sans_projet"):
            rows.append(r)
            continue
        r["start_year"] = rng.choice(["2026", "2025", "2024", "2023 ou avant"], p=[0.1, 0.35, 0.4, 0.15])
        r["role"] = rng.choice(["Patron / dirigeant(e) ET responsable du projet (les deux à la fois)", "Responsable du projet (celui ou celle qui suivait le projet au quotidien)",
                                "Responsable informatique (la personne qui s'occupe des ordinateurs et des logiciels)"], p=[0.5, 0.3, 0.2])
        r["secteur"] = rng.choice(SECTEURS, p=[0.28, 0.22, 0.07, 0.07, 0.05, 0.06, 0.05, 0.05, 0.07, 0.05, 0.03])
        r["anciennete"] = float(np.round(np.exp(rng.normal(1.8, 0.8)), 0))
        r["niveaux_hier"] = rng.choice(["2 niveaux (le patron et les employés)", "3 niveaux (le patron, des responsables, les employés)", "4 niveaux ou plus"], p=[0.5, 0.35, 0.15])
        r["form_ecrit"] = int(np.clip(np.rint(3 + 1.0 * F[i] + rng.normal(0, 0.8)), 1, 5))
        for col, thr in (("form_compta", -0.2), ("form_contrats", -0.1), ("form_organigramme", 0.1)):
            r[col] = "Oui" if F[i] + rng.normal(0, 0.8) > thr else "Non"
        npap = int(np.clip(np.rint(2.5 + 1.2 * F[i] + rng.normal(0, 0.8)), 0, 5))
        r["form_papiers"] = list(rng.choice(PAPIERS, size=npap, replace=False)) if npap > 0 else ["Je ne sais pas"]
        r["famille_propriete"] = "Oui" if famille[i] and rng.random() < 0.85 else "Non"
        r["famille_postes"] = "Oui" if famille[i] else "Non"
        r["ville"] = rng.choice(VILLES, p=[0.38, 0.17, 0.25, 0.15, 0.05])
        r["digit_niveau"] = f"Niveau {int(rng.choice([1, 2, 3, 4, 5], p=[0.15, 0.35, 0.3, 0.15, 0.05]))} — (description)"
        types = [["La communication : utiliser les réseaux sociaux"], ["La gestion de l'entreprise : utiliser des outils numériques"],
                 ["La communication : utiliser les réseaux sociaux", "La gestion de l'entreprise : utiliser des outils numériques"]]
        r["projet_type"] = types[int(rng.choice(3, p=[0.35, 0.4, 0.25]))]
        r["porteur"] = rng.choice(["Uniquement les employés de l'entreprise (personne de l'extérieur)", "Uniquement une personne ou une société de l'extérieur (agence, freelance, société informatique)",
                                   "Les deux : les employés de l'entreprise ET une personne ou une société de l'extérieur"], p=[0.45, 0.25, 0.30])
        r["sur_mesure"] = rng.choice(["Oui, fait ou adapté sur mesure", "Non, outil déjà prêt, utilisé tel quel"])
        r["financement"] = rng.choice(["L'argent de l'entreprise", "Un prêt (banque ou microfinance)", "De l'argent de la famille ou de proches"], p=[0.6, 0.2, 0.2])
        # échelles
        r["gov_unique"] = int(_likert(rng, gov[i:i + 1])[0])
        r["gov_impose"] = int(_likert(rng, gov[i:i + 1], 0.8)[0])
        r["gov_consult"] = int(_likert(rng, gov[i:i + 1], sign=-1)[0])
        r["gov_discute"] = int(_likert(rng, gov[i:i + 1], 0.8, sign=-1)[0])
        r["gov_liens"] = int(np.clip(np.rint(2 + 1.2 * famille[i] + rng.normal(0, 0.9)), 1, 5))
        r["comp_dirigeants"] = int(_likert(rng, comp[i:i + 1])[0])
        r["comp_utilisateurs"] = int(_likert(rng, comp[i:i + 1])[0])
        nb = int(rng.integers(2, 15))
        r["comp_nb_employes"] = float(nb)
        r["comp_habitues"] = float(np.clip(np.rint(nb * (0.5 + 0.2 * comp[i] + rng.normal(0, 0.2))), 0, nb))
        r["formation"] = "Oui" if rng.random() < 1 / (1 + np.exp(-(0.2 + 0.5 * comp[i]))) else "Non"
        r["formation_heures"] = float(np.round(rng.gamma(2, 6), 0)) if r["formation"] == "Oui" else None
        r["recours_externe"] = rng.choice(["Oui", "Non"])
        for col in ("com_info", "com_points", "com_alerte"):
            r[col] = int(_likert(rng, com[i:i + 1])[0])
        for col in ("dir_suivi", "dir_moyens", "dir_blocages", "dir_priorite"):
            r[col] = int(_likert(rng, sup[i:i + 1])[0])
        r["env_adequation"] = int(_likert(rng, -0.4 * z(logit)[i:i + 1])[0])
        r["env_simplicite"] = int(_likert(rng, -0.3 * z(logit)[i:i + 1])[0])
        r["env_coupures"] = int(np.clip(np.rint(3 + rng.normal(0, 1.1)), 1, 5))
        r["env_pression"] = int(np.clip(np.rint(2.6 + rng.normal(0, 1.2)), 1, 5))
        r["mois_usage"] = float(np.round(rng.gamma(2.2, 5.5), 0))
        # issue
        if kind == "en_cours":
            r.update({"usage_actuel": USAGE_COURS, "usage_taux": rng.choice(TAUX[1:3]), "arrete": "Non", "retour_ancien": "Non"})
        elif total[i]:
            r.update({"usage_actuel": USAGE_TOTAL, "usage_taux": TAUX[0], "arrete": "Oui" if rng.random() < 0.6 else "Non",
                      "retour_ancien": "Oui" if rng.random() < 0.5 else "Non"})
        elif fail[i]:
            r.update({"usage_actuel": USAGE_PARTIEL, "usage_taux": rng.choice(TAUX[1:3], p=[0.6, 0.4]), "arrete": "Non",
                      "retour_ancien": "Oui" if rng.random() < 0.25 else "Non"})
        else:
            r.update({"usage_actuel": USAGE_SUCCES, "usage_taux": rng.choice(TAUX[2:], p=[0.4, 0.6]), "arrete": "Non", "retour_ancien": "Non"})
        pool = TXT_ECHEC if (fail[i] and kind == "ok") else TXT_SUCCES
        r["txt_facteur"] = rng.choice(pool) if rng.random() < 0.8 else None
        r["txt_autre"] = rng.choice(pool) if rng.random() < 0.3 else None
        r["email"] = None
        rows.append(r)
    df = pd.DataFrame(rows)
    return df


# -------------------------------------------------------------------------------- formats Tally (tests)

def to_tally_api_payload(df: pd.DataFrame, codebook: dict) -> dict:
    """Reconstruit un objet de type réponse de l'API Tally (GET /forms/{id}/submissions)."""
    vars_ = codebook["variables"]
    questions = [{"id": v["tally_id"], "type": {"single": "MULTIPLE_CHOICE", "multi": "MULTIPLE_CHOICE", "checkbox": "CHECKBOXES", "scale": "LINEAR_SCALE",
                                                 "number": "INPUT_NUMBER", "text": "INPUT_TEXT", "email": "INPUT_EMAIL"}[v["type"]], "label": v["label"]} for v in vars_]
    subs = []
    for _, r in df.iterrows():
        resp = []
        for v in vars_:
            val = r.get(v["name"])
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            if v["type"] in ("single",):
                ans: Any = [val]
            elif v["type"] in ("multi", "checkbox"):
                ans = list(val)
            elif v["type"] == "scale":
                ans = int(val)
            elif v["type"] == "number":
                ans = float(val)
            else:
                ans = str(val)
            resp.append({"questionId": v["tally_id"], "answer": ans})
        subs.append({"id": r["_id"], "respondentId": r.get("_respondent"), "isCompleted": True,
                     "submittedAt": pd.Timestamp(r["_submitted_at"]).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "responses": resp})
    return {"page": 1, "limit": len(subs), "hasMore": False, "questions": questions, "submissions": subs}


def to_csv_text(df: pd.DataFrame, codebook: dict) -> str:
    """CSV de type export Tally : colonnes = libellés ; cases à cocher = une colonne par option."""
    cols: dict[str, list] = {"Submission ID": list(df["_id"]), "Respondent ID": list(df["_respondent"]),
                             "Submitted at": [pd.Timestamp(x).strftime("%Y-%m-%d %H:%M:%S") for x in df["_submitted_at"]]}
    for v in codebook["variables"]:
        if v["type"] == "checkbox":
            for opt in v["options"]:
                cols[f"{v['label']} ({opt})"] = ["true" if isinstance(x, list) and opt in x else "false" for x in df.get(v["name"], [None] * len(df))]
        elif v["type"] == "multi":
            cols[v["label"]] = [", ".join(x) if isinstance(x, list) else "" for x in df.get(v["name"], [None] * len(df))]
        else:
            cols[v["label"]] = ["" if (x is None or (isinstance(x, float) and np.isnan(x))) else x for x in df.get(v["name"], [None] * len(df))]
    return pd.DataFrame(cols).to_csv(index=False)
