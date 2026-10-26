// -----------------------------------------------------------------------
// data.js — chargement des données précalculées + contenus éditoriaux.
// Aucune clé API dans le front : le site ne lit que des JSON/CSV statiques
// générés par transform/build_site_data.py (charte sécurité du projet).
// -----------------------------------------------------------------------

let cache = null;

export function getData() {
  if (!cache) {
    cache = Promise.all([
      fetch(`${import.meta.env.BASE_URL}data/cities.json`).then((r) => r.json()),
      fetch(`${import.meta.env.BASE_URL}data/meta.json`).then((r) => r.json()),
    ]).then(([cities, meta]) => {
      const panel = {};
      for (const k of ["score_logement", "score_emploi", "score_demographie", "score_formation", "score_global", "taux_ancrage", "arrivees_relatives"]) {
        const vals = cities.map((c) => c[k]).filter((v) => v != null);
        panel[k] = { moy: vals.reduce((a, b) => a + b, 0) / vals.length, min: Math.min(...vals), max: Math.max(...vals) };
      }
      return { cities, meta, panel };
    });
  }
  return cache;
}

const fiches = import.meta.glob("/content/villes/*.md", { query: "?raw", import: "default", eager: true });
const articles = import.meta.glob("/content/articles/*.md", { query: "?raw", import: "default", eager: true });

export function ficheVille(slug) {
  return fiches[`/content/villes/${slug}.md`] || null;
}

export const listeArticles = [
  { slug: "ou-rester-apres-etudes", poids: "signature", tag: "Mobilité" },
  { slug: "paradoxe-villes-abordables", tag: "Logement" },
  { slug: "logement-goulot", tag: "Logement" },
  { slug: "paris-logement-hors-budget", tag: "Focus ville" },
  { slug: "lyon-regularite", tag: "Focus ville" },
  { slug: "emploi-sante-marche", tag: "Emploi" },
  { slug: "rester-ou-partir-distance", tag: "Mobilité" },
  { slug: "vie-etudiante-taille-densite", tag: "Vie étudiante" },
];

export function contenuArticle(slug) {
  return articles[`/content/articles/${slug}.md`] || null;
}

export function titreArticle(slug) {
  const titres = {
    "ou-rester-apres-etudes": "Où reste-t-on après avoir étudié ?",
    "paradoxe-villes-abordables": "Le paradoxe des villes abordables",
    "logement-goulot": "Le logement, goulot d'étranglement",
    "paris-logement-hors-budget": "Paris : deux piliers dominés, un logement hors budget",
    "lyon-regularite": "Lyon : la régularité plutôt que la spécialisation",
    "emploi-sante-marche": "Emploi : la santé du marché du travail local",
    "rester-ou-partir-distance": "Rester ou partir ? L'effet distance",
    "vie-etudiante-taille-densite": "Vie étudiante : taille de ville contre densité étudiante",
  };
  return titres[slug] || slug;
}
