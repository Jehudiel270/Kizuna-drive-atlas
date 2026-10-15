# Du protocole aux pages de l'outil

Ce document relie chaque exigence du protocole (ICPM_KIZUNA_Phase1) à ce que l'outil calcule, à la page qui le montre et à la règle de décision.
Le plan exécutable est `api/app/config/plan.yaml` (versionné par empreinte ; modifiable dans *Plan d'analyse*).

## Variable dépendante : l'issue du projet (protocole 3.5)
| Issue | Règle (formulaire Tally) |
|---|---|
| **Échec total** | « On ne l'utilise presque plus » **ou** projet arrêté avant d'être terminé |
| **Échec partiel** | « Il fonctionne, mais seulement… » **ou** retour aux anciennes méthodes **ou** moins de 50 % des utilisateurs concernés |
| **Succès** | « Il fonctionne et il est utilisé régulièrement » **et** aucun des critères d'échec partiel ci-dessus |
| *En cours* | **exclu** des modèles (on ne peut pas classer un projet non terminé) ; compté et signalé dans le suivi de collecte |

Analyse principale : **échec (partiel + total) vs succès**, binaire. Robustesse : ordinale (3 modalités), échec total vs succès, contrôles étendus TOE, projets ≥ 6 mois d'usage, maximum de vraisemblance sans pénalisation, Firth systématique.
Réponses incohérentes (ex. « arrêté » mais « utilisé régulièrement ») : signalées dans *Suivi de collecte*.

## Hypothèses → modèles → décisions
| Hyp. | QS / OS | Modèle et test | Décision (verdict) |
|---|---|---|---|
| **H1** gouvernance centralisée ↑ échec | QS1 / OS1 | Modèle A : logit ~ gouvernance + contrôles ; OR par écart-type | *Soutenue* si OR > 1 et p Holm < 0,05 ; *Partielle* si p < 0,05 avant Holm seulement ; *Contredite* si significatif en sens inverse |
| **H2** faibles compétences ↑ échec | QS2 / OS2 | Modèle B (multiple) : effet net de compétences | idem H1 |
| **H3** le soutien de la direction atténue les effets | QS3 / OS3 | Modèle C : + 3 interactions soutien × (gouvernance, compétences, communication) ; **test du rapport de vraisemblance conjoint (3 ddl)** + courbes de probabilité prédite | *Soutenue* : LR significatif (Holm) et sens atténuant ; *Partielle* : une interaction seulement ou non robuste à Holm ; *Non soutenue* si direction hétérogène ; *Contredite* si une interaction significative amplifie le risque |
| **H4** formalisation modère gouvernance → échec ; effet plus fort si familial/informel | QS4 / OS4 | Modèle D : gouvernance × formalisation (3 catégories), LR 2 ddl ; **tendance linéaire** informel→formel ; interaction gouvernance × propriété familiale ; effets simples par catégorie | *Soutenue* : interaction significative (Holm) **et** profil décroissant ; *Partielle* si significative mais profil non décroissant |
| **H5** faible communication ↑ échec | QS5 / OS5 | Modèle B : effet net de communication | idem H1 |

Correction de **Holm** sur les 5 tests principaux. α = 0,05.

## Cohérence statistique (garde-fous automatiques)
- **EPV** (échecs par paramètre) < 10 → régression de **Firth** + avertissement (très probable avec 150–180 projets : il faut garder peu de contrôles).
- **VIF** > 5 signalé ; **AUC**, Hosmer-Lemeshow, R² de McFadden/Nagelkerke, ROC, calibration (page *Modèles*).
- **Puissance** : OR minimal détectable à 80 %/90 % (page *Puissance*) — à citer dans les limites.
- **Fiabilité** : α de Cronbach ≥ 0,70 (protocole 4.10), IC bootstrap, ω, Spearman-Brown pour les échelles à 2 items.
- Moins de 40 projets complets → hypothèses « non testables » ; moins de 60 → réseau exploratoire verrouillé.

## Où voir quoi
| Besoin du protocole | Page |
|---|---|
| Échantillonnage, quotas secteur × taille, éligibilité (4.5) | *Suivi de collecte* |
| Connexion du formulaire, doublons, exclusions tracées | *Données & Tally* |
| Statistiques descriptives, ANOVA / Khi² (5.1–5.2) | *Descriptif & comparaisons* |
| Fiabilité (4.10) | *Fiabilité des échelles* |
| Régressions et hypothèses (5.3) | *H1…H5*, *Modèles & diagnostics* |
| Analyse de contenu thématique (5.4), accord inter-codeurs | *Analyse qualitative* |
| Cadre conceptuel (3.6) avec effets estimés, réseau exploratoire | *Carte 3D* |
| Limites, reproductibilité, rapport de collecte | *Rapport & exports* |

## Décisions de l'outil à faire valider par l'équipe (non écrites dans le protocole)
1. **Indice de formalisation** : moyenne de (échelle « écrit/organisé »), (part de oui : comptabilité, contrats, organigramme), (papiers : IFU, RCCM, « entreprenant », sécurité sociale, compte pro) ; seuils informel < 0,34 ≤ semi-formel < 0,67 ≤ formel.
2. **Règle « échec partiel »** (taux d'usage < 50 %, retour aux anciennes méthodes) et **échec total** si projet arrêté.
3. **Regroupements** de secteurs (Commerce / Services / Production & BTP / Autre) et de tailles (< 10 / 10–49 / 50+) pour limiter les paramètres.
4. **Quotas cibles** (à saisir : `quotas.secteur_g`, `quotas.taille_g`, `quotas.ville`).
5. **Soutien de la direction** : moyenne de 4 items ; les 3 interactions de H3 sont testées ensemble (LR) plutôt qu'une par une.

## Limites à écrire dans le rapport
- Échantillon non probabiliste (choix raisonné) : pas de généralisation à toutes les PME béninoises.
- La question 5 (entreprise déclarée) exclut les structures strictement informelles : la formalisation varie surtout *entre* entreprises déclarées.
- Un seul répondant par projet (biais de mesure commun) ; échelles auto-déclarées.
- Les projets « en cours » ne sont pas classables (biais de survie possible).
- Puissance limitée pour les interactions (H3, H4) : un résultat non significatif n'est pas une preuve d'absence d'effet.
