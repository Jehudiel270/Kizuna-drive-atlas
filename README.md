# KIZUNA ATLAS — outil d'analyse du protocole KIZUNA DRIVE (ICPM Challenge 2026)

Site complet (front + API + base de données) qui se branche sur le formulaire Tally `446dvO` et répond aux **5 hypothèses du protocole**
(gouvernance, compétences, soutien de la direction, formalisation, communication → échec des projets de digitalisation des PME),
avec suivi de collecte, fiabilité des échelles, régressions logistiques, analyse qualitative, carte 3D et rapport exportable.

```
api/    FastAPI + SQLAlchemy + pandas/statsmodels   (Render / Railway, Docker)     → tests : pytest (19)
web/    Next.js 15 + three.js                         (Vercel)
docs/   DEPLOIEMENT.md · ARCHITECTURE.md · PLAN_ANALYSE.md
render.yaml · docker-compose.yml
```

**Démarrer** : lire `docs/DEPLOIEMENT.md` (base Neon → API Render → front Vercel → webhook Tally).
**Comprendre les choix scientifiques** : `docs/PLAN_ANALYSE.md`. **Structure du code** : `docs/ARCHITECTURE.md`.

## Essai local en 2 minutes (données simulées)
```bash
cd api && pip install -r requirements.txt && DEMO_MODE=true uvicorn app.main:app      # API sur :8000
cd web && npm install && cp .env.example .env.local && npm run dev                   # site sur :3000
```
Les données simulées contiennent des effets plantés pour vérifier que l'outil les retrouve : **elles ne disent rien sur les PME réelles**.

## Utilisation pendant la collecte
1. *Données & Tally* : vérifier la connexion, la couverture du questionnaire ; exclure doublons/tests (motif obligatoire).
2. *Suivi de collecte* : corriger le recrutement tant qu'il est temps (quotas, relais dominant, enquêteurs).
3. *Plan d'analyse* : renseigner les quotas ; valider les 5 décisions listées dans `docs/PLAN_ANALYSE.md`.
4. Fin de collecte : **figer un instantané**, le sélectionner, parcourir H1–H5, coder les réponses ouvertes (2 codeurs), puis *Rapport & exports*.

Licence et données : les réponses de l'enquête restent la propriété de l'équipe de recherche ; ne jamais committer de `.env`.
