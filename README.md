# Alizé

Observatoire data de la mobilité étudiante en France. 20 villes universitaires notées sur 4 piliers à partir de 6 sources open data, avec une question en fil conducteur : où reste-t-on après avoir étudié ?

Site en ligne : https://alize-iota.vercel.app

## Ce que fait le projet

- Collecte et normalise des données publiques (INSEE, MESR, DGFiP, France Travail) via un pipeline Python entièrement scripté.
- Calcule un score d'attractivité par ville, décomposé en 4 piliers : logement, emploi, démographie, formation.
- Met en évidence la mobilité étudiante en trois temps : qui vient étudier où, qui reste après, et où partent les autres.
- Restitue le tout dans un site React : carte interactive, classement avec pondération réglable, fiches villes, quiz de recommandation et simulateur de scénarios.

## La découverte signature

Le croisement des données de mobilité révèle un cas contre-intuitif. Aix-en-Provence envoie plus d'étudiants qu'elle n'en accueille (0,82 entrée pour une sortie), retient le moins bien ses jeunes diplômés (78,2 % d'ancrage)... et attire pourtant le plus d'arrivées de diplômés du panel (21,8 % par an). Former ne veut pas dire retenir, et retenir ne veut pas dire attirer. L'ensemble des villes montre d'ailleurs un taux d'ancrage homogène (78 à 85,5 %) : ce qui les départage n'est pas la fidélité de leurs diplômés, mais le renouvellement par les arrivées.

Autres enseignements issus des données :

- Nancy, Rennes et Lyon forment le trio de tête du classement général, robuste à 6 scénarios de pondération.
- Paris cumule les extrêmes : pilier formation maximal (100), pilier logement nul (prix médian 9 774 €/m², le plus cher du panel).
- L'élasticité prix-densité étudiante testée par régression n'est pas significative (n = 19, R² = 0,38) : impossible d'affirmer que les étudiants font monter les prix. Le seul coefficient significatif lie chômage et prix (-10 % de prix par point de chômage).

## Architecture du dépôt

```
src/extract/        Extraction des sources open data (1 script par source)
  01_mestr.py           Effectifs étudiants par commune (MESR/SIES)
  02_melodi.py          Recensement INSEE : âge, diplômes, PCS (API MELODI)
  03_melodi_emploi.py   Taux de chômage au RP (API MELODI)
  03_marche_travail.py  Marché du travail France Travail (gelé, voir journal)
  05_dvf.py             Prix médian du m² (DVF DGFiP)
  06_api_geo.py         Référentiel des 20 villes (API Géo)
  07_flux_mobilites.py  Flux scolaires entrants/sortants par ville
  08_detail_mobilites.py Profil détaillé des étudiants accueillis
  09_migrations_residentielles.py  Ancrage des diplômés 20-29 ans

transform/          Calculs et produits analytiques
  scores.py             Scores par pilier + score global (villes_scoring.csv)
  sensibilite.py        Robustesse du classement sur 6 scénarios de poids
  regression.py         Élasticité prix-densité (OLS + bootstrap 2000)
  simulateur.py         Scénarios what-if avec garde-fous
  quiz.py               Moteur de recommandation pondérée

data/processed/     Sorties versionnées (alimentent le site)
site/               Site React (Vite) + générateur de ses données
```

## Sources de données

Toutes les sources sont publiques et gratuites : API MELODI de l'INSEE (recensement 2023, migrations résidentielles, mobilités scolaires), fichiers du MESR/SIES (effectifs étudiants, rentrée 2025-26), DVF de la DGFiP (transactions immobilières 2025, trim 5-95 %), API Géo. Les fichiers volumineux (détail RP, jusqu'à 1,9 Go) sont téléchargés manuellement depuis les pages officielles INSEE et non versionnés.

## Méthodologie du score

Chaque indicateur est normalisé en 0-100 sur le panel des 20 villes (min-max orienté attractivité : un prix élevé donne un score bas). Les piliers agrègent des indicateurs pondérés : logement (prix, taux d'effort), emploi (chômage, parts de cadres et professions intermédiaires), démographie (densité étudiante, part des 15-24 ans), formation (effectifs, part de diplômés du supérieur). Le score global pondère les piliers 30/25/25/20.

Les scores sont relatifs au panel : ils comparent les villes entre elles, ils ne notent pas une qualité de vie absolue. L'analyse de sensibilité (6 scénarios de pondération, rejoués dans `sensibilite.py`) montre que le trio de tête est stable mais que le milieu de classement dépend fortement des poids. La régression et ses intervalles de confiance sont documentées dans l'onglet La démarche du site.

## Reproductibilité

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt

python src/extract/06_api_geo.py          # référentiel (sans clé)
python src/extract/01_mestr.py            # nécessite le CSV MESR téléchargé
python src/extract/02_melodi.py           # API MELODI, sans clé
python src/extract/03_melodi_emploi.py
python src/extract/05_dvf.py             # télécharge le zip DVF lui-même
python transform/scores.py               # produit data/processed/villes_scoring.csv
python transform/sensibilite.py
python transform/regression.py
```

Pour le site :

```bash
cd site
npm install
python transform/build_site_data.py   # régénère les données du site depuis les CSV
npm run dev                           # http://localhost:5173
npm run build                         # build de production
```

Les scripts de mobilité (07, 08, 09) demandent les fichiers INSEE correspondants dans `data/raw/` (téléchargement manuel, noms documentés en tête de chaque script). Les scripts d'extraction gèrent les particularités de découpage : arrondissements municipaux de Paris, Lyon et Marseille sommés côté source, codes INSEE divergents entre sources résolus par repli sur le nom normalisé.

## Journal de bord d'ingénierie

Les impasses font partie du projet. Les principales, documentées pour la reproductibilité :

- **Pivot DDL vers MELODI.** L'API Données Locales de l'INSEE, prévue au départ pour le recensement, s'arrête le 01/12/2026. Toute la partie RP a été migrée vers la nouvelle API MELODI, sans clé. Le filtre par commune y demande une syntaxe par département avec préfixe (`DEP-69*COM` et `DEP-69*ARM` séparés, sinon erreur 500) et l'API plafonne certaines réponses à 100 000 lignes : les filtres de dimensions doivent être passés dans l'URL, pas filtrés après coup.
- **Abandon du CSV Cerema pour l'immobilier.** L'espace de téléchargement exige un compte, contraire à l'exigence de sources libres d'accès. Retour au DVF brut de la DGFiP sur data.gouv : zip de 71 Mo, séparateur pipe, virgules décimales françaises, et Strasbourg absent (droit local alsacien-mosellan). Le prix y est imputé à la médiane des 19 autres villes pour le score uniquement, la valeur affichée reste vide.
- **France Travail en attente.** L'abonnement à l'API Marché du travail est actif, le jeton OAuth2 porte le bon scope (découvert par énumération, la documentation ne le publie pas), mais tous les appels renvoient 403. Ticket INC2760848 ouvert auprès du support. Le pilier emploi a été construit via MELODI à la place, la requête d'offres par métiers étudiants reste en attente de déblocage.
- **Pièges de découpage géographique.** Paris et Lyon publiés par arrondissements dans le RP et dans les effectifs du MESR, avec des codes INSEE différents selon les sources (Lyon 69123, 69381, 69389...). Chaque script somme les arrondissements côté source et normalise les codes ; les replis par nom de ville sont tracés en console.
- **Géolocalisation.** L'API Géo ne renvoie les coordonnées que sur la requête par code avec `fields=centre`, pas sur la recherche par nom, et le format est GeoJSON `[lon, lat]`, pas latitude puis longitude. Détecté après deux échecs silencieux.
- **Déploiement.** Les déploiements automatiques depuis GitHub échouaient (exit 127 : `vite` introuvable) car Vercel buildait depuis la racine du dépôt, sans `package.json`. Le répertoire racine du projet est `site/`, corrigé dans la configuration.

## Limites assumées

- Le score compare 20 villes entre elles, il ne mesure pas une qualité de vie absolue.
- Paris est la commune seule (ses effectifs étudiants incluent la petite couronne), Grenoble est sous-estimé (campus principal à Saint-Martin-d'Hères).
- Le taux de chômage est celui du recensement (déclaratif), plus élevé que le taux BIT : la hiérarchie entre villes reste plausible, l'ordre de grandeur est discuté sur le site.
- La mobilité des diplômés se lit via la résidence un an avant l'enquête, pas cinq ans ; la fenêtre est 20-29 ans en emploi.
- Les flux inter-villes inférieurs à 200 personnes (données du RP) sont des ordres de grandeur, pas des comptes exacts.

## Usage des outils d'IA

Le prototypage a été assisté par des outils d'IA (génération de scripts, relecture). Le cadrage méthodologique, les choix de sources, la validation des chiffres, les tests d'exécution et chaque décision d'architecture ont été faits et revus manuellement. Les limites ci-dessus et le journal de bord sont là pour que chaque ligne de résultat soit défendable.

## Feuille de route

- Traduction anglaise de l'interface
- Requête d'offres d'emploi étudiant par codes ROME (dès le déblocage France Travail)
- Tests unitaires sur les pièges documentés (ARM, filtres MELODI, jointures DVF)
- Actualisation annuelle des données (millésime DVF 2026 en réserve)

## Auteur

Samuel Amouzou, projet personnel data, conçu pour mesurer une question réelle avec des données publiques.
