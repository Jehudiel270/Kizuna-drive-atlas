# Architecture

```
web/  (Next.js 15, React 19, three.js / react-three-fiber)       api/  (FastAPI, SQLAlchemy 2)
 ├─ app/…            15 pages (client components)                 ├─ app/main.py          application + CORS + routes
 ├─ components/      Shell, ui, charts (SVG), Scene3D (WebGL)     ├─ app/routers/         auth, ingest, config, analysis, quali, snapshots, report
 └─ lib/             client API, formats FR                       ├─ app/service.py       chargement (live | snapshot | démo) + cache de résultats
                                                                  ├─ app/analysis.py      fonctions d'analyse (utilisées par routes ET rapport)
                                                                  ├─ app/core/            codebook→variables, issue, scores, formalisation, données simulées
                                                                  ├─ app/stats/           logit/Firth, hypothèses, fiabilité, descriptif, collecte, texte, réseau, puissance
                                                                  ├─ app/config/          plan.yaml (plan pré-enregistré), codebook.yaml (60 variables Tally)
                                                                  └─ tests/               19 tests (normalisation, règles d'issue, Firth, Holm, API de bout en bout)
```

## Flux de données
1. **Ingestion** : webhook / API Tally / CSV → `normalize_*` (appariement par id de question puis par libellé, cases à cocher regroupées, e-mail haché) → table `submissions` (JSON, idempotent par id de soumission).
2. **Jeu analysable** : `build_dataset` ajoute éligibilité, issue (succès / échec partiel / échec total / en cours), scores des échelles (items inversés, ≥ 50 % d'items), orientation « risque », indice de formalisation, contrôles regroupés.
3. **Analyses** : fonctions pures sur le DataFrame, mises en cache par (données, plan). Le cache est invalidé à toute nouvelle soumission ou modification du plan.
4. **Instantanés** : copie figée des lignes + plan + codebook + SHA-256. Toutes les routes d'analyse acceptent `?snapshot=ID`.
5. **Rapport** : mêmes fonctions → blocs neutres → Markdown / DOCX / XLSX / ZIP de reproductibilité.

## Tables
`users`, `submissions`, `settings` (surcharges du plan/codebook, dernière synchro), `snapshots`, `themes`, `coded_segments`, `audit_log`.
JSON natif (JSONB sous Postgres). SQLite uniquement pour les tests et le développement.

## Principaux endpoints (`/docs` pour le détail)
`POST /auth/login` · `POST /ingest/webhook/tally` · `POST /ingest/sync` · `POST /ingest/csv` · `GET /ingest/status|submissions` · `PATCH /ingest/submissions/{id}` ·
`GET /analysis/overview|collecte|coverage|descriptif|crosstabs|fiabilite|hypotheses|hypotheses/{H1..H5}|modeles|puissance|keyness|graph/modele|graph/exploratoire|graph/export` ·
`GET/PUT /config/plan|codebook` · `/quali/themes|answers|code|synthesis|kappa` · `/snapshots` · `GET /report/preview|markdown|docx|xlsx|package`.

## Choix à connaître
- **Régression logistique** (statsmodels) ; **Firth** implémenté en interne (pas de dépendance fragile) et activé automatiquement si EPV < 10 ou séparation.
- **Réseau exploratoire** : corrélations partielles de Spearman régularisées (graphical lasso, EBIC), bootstrap des arêtes, CS-coefficient ; verrouillé si n < 60 ou CS < 0,25.
- **Pas de calcul dans le navigateur** : le front n'affiche que des résultats serveur (une seule source de vérité, reproductible).
