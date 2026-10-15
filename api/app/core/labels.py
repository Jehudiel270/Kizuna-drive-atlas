"""Libellés courts des variables (graphiques, tableaux, réseau)."""
SHORT = {
    "form_ecrit": "Choses écrites et organisées",
    "gov_unique": "Décisions prises par une seule personne",
    "gov_consult": "Équipe consultée avant les décisions",
    "gov_discute": "Décisions discutables par l'équipe",
    "gov_impose": "Outil/prestataire imposé à l'équipe",
    "gov_liens": "Liens familiaux/amicaux dans les décisions",
    "comp_dirigeants": "Dirigeants du projet compétents",
    "comp_utilisateurs": "Utilisateurs à l'aise avec le numérique",
    "com_info": "Information bien partagée",
    "com_points": "Points réguliers dans l'équipe",
    "com_alerte": "Problèmes remontés vite au patron",
    "dir_suivi": "Direction : suivi de près",
    "dir_moyens": "Direction : moyens donnés",
    "dir_blocages": "Direction : intervient sur les blocages",
    "dir_priorite": "Direction : projet prioritaire",
    "env_adequation": "Outil adapté aux besoins",
    "env_simplicite": "Outil simple à utiliser",
    "env_coupures": "Coupures électricité/Internet",
    "env_pression": "Pression externe pour lancer le projet",
    "echec": "Échec du projet (0/1)",
}


def short_labels(codebook: dict) -> dict[str, str]:
    out = {v["name"]: v["label"] for v in codebook["variables"]}
    out.update(SHORT)
    return out
