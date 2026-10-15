# Déploiement de KIZUNA ATLAS (4 morceaux séparés)

```
Tally (formulaire 446dvO) ──webhook signé──▶  API FastAPI (Render / Railway, Docker)  ◀──HTTPS──  Front Next.js (Vercel)
                          ◀──API (sync)────                │
                                                           ▼
                                                 Postgres (Neon)
```

| Morceau | Où | Pourquoi là |
|---|---|---|
| Base de données | **Neon** (Postgres gratuit, région UE) | gratuite, sauvegardes, aucune maintenance |
| API (Python) | **Render** (ou Railway) en conteneur Docker | pandas + statsmodels + scikit-learn dépassent la limite de taille des fonctions serverless de Vercel (250 Mo) et un calcul dure plusieurs secondes ; il faut un serveur « toujours allumé » pour recevoir le webhook |
| Front (Next.js) | **Vercel** | déploiement automatique à chaque `git push` |
| Collecte | **Tally** | webhook (temps réel) + clé API (rattrapage) |

Ordre à suivre : **1 Base → 2 API → 3 Front → 4 Tally → 5 Vérifications**. Compter ~40 minutes.

## 0. Préparer le dépôt GitHub
```bash
cd kizuna-atlas
git init && git add . && git commit -m "KIZUNA ATLAS"
# créer un dépôt privé sur GitHub puis :
git remote add origin git@github.com:VOTRE-COMPTE/kizuna-atlas.git && git push -u origin main
```
Générer deux secrets (à garder dans un gestionnaire de mots de passe) :
```bash
openssl rand -hex 32   # → JWT_SECRET
openssl rand -hex 16   # → EMAIL_SALT   (ne JAMAIS le changer après le début de la collecte)
```

## 1. Base de données — Neon
1. https://neon.tech → *Create project* → nom `kizuna`, région **Europe (Frankfurt)**, Postgres 16.
2. Onglet *Dashboard* → *Connection string* → cocher **Pooled connection** → copier l'URL
   `postgresql://user:motdepasse@ep-xxx-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require`.
3. C'est tout : **les tables sont créées automatiquement** au premier démarrage de l'API (pas de migration à lancer).

> Neon met la base en veille après 5 min d'inactivité (gratuit) ; le premier appel suivant prend ~1 s de plus. Sans conséquence.

## 2. API — Render
1. https://render.com → *New +* → **Web Service** → connecter le dépôt GitHub.
2. Réglages : **Root Directory** `api` · **Runtime** `Docker` · **Health Check Path** `/health` · plan **Free**.
   *(Le service gratuit s'endort après 15 min sans trafic, puis met environ une minute à redémarrer. Le système de fichiers est éphémère : les données doivent rester dans Neon, jamais dans un fichier SQLite local. Un webhook Tally peut expirer pendant le réveil ; utilisez « Synchroniser » pour rattraper les réponses. Ce plan convient aux essais, mais pas à une collecte de production nécessitant une réception fiable en temps réel.)*
   Alternative : `render.yaml` à la racine → *New + → Blueprint*.
3. *Environment* — ajouter :

| Variable | Valeur |
|---|---|
| `DATABASE_URL` | l'URL Neon de l'étape 1 |
| `JWT_SECRET` | secret généré (étape 0) |
| `EMAIL_SALT` | secret généré (étape 0) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | votre compte administrateur (créé au 1er démarrage, mot de passe long) |
| `TALLY_FORM_ID` | `446dvO` |
| `TALLY_API_KEY` | voir étape 4a |
| `TALLY_SIGNING_SECRET` | voir étape 4b (inventez-le maintenant : `openssl rand -hex 16`) |
| `CORS_ORIGINS` | l'URL du front (étape 3), ex. `https://kizuna-atlas.vercel.app` — à compléter après l'étape 3 |
| `DEMO_MODE` | `false` |

4. *Create Web Service*. Quand c'est « Live », ouvrir `https://VOTRE-API.onrender.com/health` → `{"status":"ok",...}`.
   La doc interactive de l'API est sur `/docs`.

**Variante Railway** : *New Project → Deploy from GitHub → Root Directory `api`* (détecte le Dockerfile), mêmes variables, *Settings → Networking → Generate Domain*.

## 3. Front — Vercel
1. https://vercel.com → *Add New → Project* → importer le dépôt.
2. **Root Directory** : `web` (Framework : Next.js détecté automatiquement).
3. *Environment Variables* :

| Variable | Valeur |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://VOTRE-API.onrender.com` (sans `/` final) |

4. *Deploy*. Copier l'URL obtenue, puis **retourner sur Render** et mettre cette URL dans `CORS_ORIGINS`
   (plusieurs origines possibles, séparées par des virgules ; pour accepter les URLs de prévisualisation Vercel : `CORS_ORIGIN_REGEX=https://kizuna-atlas.*\.vercel\.app`).
5. Ouvrir l'URL Vercel → connexion avec `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

> Toute variable `NEXT_PUBLIC_*` est figée au *build* : après modification, faire *Redeploy* sur Vercel.

## 4. Tally
**4a. Clé API (synchronisation / rattrapage)** — Tally → *Settings → API keys → Create API key* → copier dans `TALLY_API_KEY` (Render).

**4b. Webhook (temps réel)** — Tally → ouvrir le formulaire → *Integrations → Webhooks → Connect* :
- **Endpoint URL** : `https://VOTRE-API.onrender.com/ingest/webhook/tally`
- **Signing secret** : exactement la valeur de `TALLY_SIGNING_SECRET`
- Enregistrer, puis utiliser le bouton de test de Tally (*Send test event*).

**Rappel important** : le formulaire doit être **publié**, et les modifications de questions ne s'appliquent aux répondants qu'après *Publish*.
Si une question est renommée ou remplacée dans Tally, vérifier *Données → Couverture du questionnaire* (le codebook relie par identifiant de question **et** par libellé).

## 5. Vérifications (check-list de mise en service)
- [ ] `GET /health` → `ok` ; connexion au site réussie.
- [ ] *Données & Tally* : « secret configuré » et « clé API configurée » en vert.
- [ ] Bouton **Synchroniser maintenant** → N réponses lues (l'historique des tests apparaît).
- [ ] Soumettre une réponse de test dans Tally → elle apparaît dans *Soumissions* en < 30 s (webhook) et *Dernière réception* se remplit.
- [ ] *Couverture du questionnaire* : aucune variable à 0 % sur la réponse de test complète.
- [ ] **Juste avant de lancer la vraie collecte** : *Données → Zone sensible → Supprimer toutes les soumissions* (purge des tests), puis relancer une synchro.
- [ ] Remplir les **quotas** (secteur × taille) dans *Plan d'analyse → Modifier le plan* (voir `PLAN_ANALYSE.md`).
- [ ] Créer les comptes des coéquipiers (Swagger `/docs` → `POST /auth/users`, rôle `analyste` ou `lecteur`) — chaque codeur qualitatif doit avoir son propre compte.
- [ ] À la fin de la collecte : *Données → Instantanés figés → Figer maintenant*, sélectionner l'instantané, puis *Rapport & exports*.

## Démonstration publique sans données réelles (optionnel)
Deuxième service API avec `DEMO_MODE=true` (aucune authentification, données **simulées**) : sert à montrer l'outil dans le rapport sans exposer de données. Le bandeau « données simulées » est activé par l'API.

## Développement local
```bash
# API
cd api && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt
DEMO_MODE=true uvicorn app.main:app --reload          # http://localhost:8000/docs
pytest                                                # 19 tests
python -m scripts.make_csv 165 > simule.csv           # CSV simulé au format Tally pour tester l'import
# Front
cd web && cp .env.example .env.local && npm install && npm run dev   # http://localhost:3000
# Tout-en-un (Postgres + API) : docker compose up --build
```

## Sécurité et données personnelles
- Les e-mails sont **hachés (SHA-256 salé)** à la réception : l'adresse n'est jamais stockée en clair. Les textes libres peuvent contenir des noms : l'export « paquet de reproductibilité » les exclut.
- Mots de passe hachés (bcrypt), jetons JWT 12 h, rôles `admin` > `analyste` > `lecteur`. Webhook refusé sans signature valide.
- Toute modification du plan, exclusion de réponse, purge ou instantané est journalisé (*Plan d'analyse → Journal*).
- Sauvegardes : Neon conserve l'historique (restauration à un instant donné) ; en complément, l'instantané + le paquet ZIP sont des copies figées exportables.

## Dépannage
| Symptôme | Cause probable |
|---|---|
| Le site affiche « API injoignable » | `NEXT_PUBLIC_API_URL` faux, ou API en veille (plan gratuit) : ouvrir `/health` puis recharger |
| Erreur CORS dans la console du navigateur | l'URL du front n'est pas dans `CORS_ORIGINS` (pas de `/` final, `https://` inclus) |
| Webhook Tally « 401 » | `TALLY_SIGNING_SECRET` différent de celui saisi dans Tally ; en dernier recours, utiliser *Synchroniser* |
| Webhook « 503 » | `TALLY_SIGNING_SECRET` absent côté API |
| Variable à 0 % dans la couverture | question modifiée dans Tally : mettre à jour le codebook (*Plan d'analyse → Codebook*) |
| Hypothèses « non testables » | pas assez de projets classables (min. 40 pour les modèles) — normal en début de collecte |
| Réseau 3D « verrouillé » | moins de 60 projets complets : c'est voulu (réseau instable) |
