# Alizé — site public (Vite + React)

Site vitrine de l'Atlas de l'attractivité étudiante : observatoire data + webzine sur la mobilité étudiante. Portage du prototype validé (canvas v2), repositionné sur le finding signature mobilité (« où reste-t-on après avoir étudié ? »).

## Installation

Le dossier `site/` se place à la racine du dépôt `edu-move` (à côté de `src/` et `data/`).

```bash
cd site
npm install
npm run dev        # http://localhost:5173
```

## Données

**Aucune clé API dans le front.** Le site ne lit que des fichiers statiques :

- `public/data/cities.json` + `meta.json` — fournis, déjà générés depuis `data/processed/villes_scoring.csv` (commit 17/10/2026) + les KPI mobilité (article signature, scripts 07/08/09).
- Pour régénérer depuis tes CSV locaux (recommandé au premier lancement, ça remplit ratio_attractivite et part_18_24_accueillis pour les 20 villes) :

```bash
python site/transform/build_site_data.py
```

Le script lit `data/processed/villes_scoring.csv` (obligatoire) et les CSV de `data/raw/` (optionnels : champs à null si absents, le site affiche « à venir »).

## Contenus éditoriaux

- `content/villes/{slug}.md` — les 20 fiches villes (récupérées de Notion, tables nettoyées).
- `content/articles/{slug}.md` — les 8 articles, dont l'article signature mobilité.

Rendus par `react-markdown` + `remark-gfm`.

## Pages

| Route | Contenu |
| --- | --- |
| `/` | Hero repositionné sur le finding Aix (éducatrice vs gagnante), carte France SVG (22 régions, contours simplifiés), top 5, encart ancrage × arrivées |
| `/classement` | 20 villes triables + **curseurs de pondération** en direct + CSV téléchargeable |
| `/ville/:slug` | Dashboard (piliers, radar vs moyenne, KPI, distribution, voisines) + fiche intégrale |
| `/quiz` | Portage fidèle de `transform/quiz.py` : question 0 commune via API Géo (sans clé, jamais bloquante), 7 questions, filtre 300 km, transparence des poids |
| `/simulateur` | Portage de `transform/simulateur.py` : scénarios cumulables, recalcul min-max du panel, garde-fous non bloquants, disclaimer causalité |
| `/articles` + `/articles/:slug` | Les 8 analyses data-driven |
| `/demarche` | Sources, formule du score, robustesse 6 scénarios, élasticité non significative, limites, reproductibilité |

Interface FR/EN (contenus en FR, traduction progressive).

## Déploiement (Vercel)

```bash
npm i -g vercel   # une fois
vercel             # preview
vercel --prod      # production
```

`vercel.json` gère le rewrite SPA (routes `/ville/…` partageables). Framework preset : Vite, build `npm run build`, output `dist`.

## À faire ensuite (feuille de route)

- [ ] SEO : méta OG par page (react-helmet-async), sitemap
- [ ] Compartimenter Strasbourg dans le simulateur (prix de départ imputé : déjà noté à l'écran)
- [ ] Traduction EN des contenus
- [ ] Vérifier la matrice du quiz contre `transform/quiz.py` après le 1er lancement (le moteur est identique, les textes peuvent diverger légèrement)
- [ ] `npm audit` + Dependabot (checklist sécurité projet)
- [ ] En-têtes de sécurité Vercel (CSP)

## Notes techniques

- Les scores/piliers affichés viennent du CSV authentique ; les piliers manquants dans les fiches (formation Rennes/Caen/Aix/Angers, démographie Dijon) sont couverts par le CSV, aucune dérivation n'est nécessaire côté site.
- `src/lib/scoring.js` reproduit exactement les formules de `transform/scores.py` (min-max 0-100, piliers, poids 30/25/25/20) : le classement à curseurs, le quiz et le simulateur partagent ce module.
- La carte utilise un contour régional simplifié (découpage antérieur à 2016, source ouverte) : mention crédits affichée sous la carte.
