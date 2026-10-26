// -----------------------------------------------------------------------
// scoring.js — moteur de score partagé (classement, quiz, simulateur).
// Reproduit EXACTEMENT transform/scores.py / simulateur.py :
// min-max 0-100 sur le panel, piliers, poids 30/25/25/20.
// -----------------------------------------------------------------------

export const W_DEFAUT = { logement: 0.30, emploi: 0.25, demographie: 0.25, formation: 0.20 };

// Strasbourg : prix DVF indisponible (droit local) — imputé à la médiane
// du panel POUR LE SCORE UNIQUEMENT (documenté dans La démarche).
export const PRIX_STRASBOURG_IMPUTE = 3391.1;

export function minmax(values, { inverser = false } = {}) {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  if (hi === lo) return values.map(() => 50);
  return values.map((v) => {
    const s = (100 * (v - lo)) / (hi - lo);
    return inverser ? 100 - s : s;
  });
}

// Taux d'effort (%) d'un studio 20 m², budget étudiant 800 €/mois,
// loyer ≈ 0,5 % de la valeur d'achat par mois (heuristique documentée).
export function effortDepuisPrix(prix) {
  return (100 * (0.005 * prix * 20)) / 800;
}

export function prixEffectif(c) {
  if (c.prix_m2 != null) return c.prix_m2;
  return c.slug === "strasbourg" ? PRIX_STRASBOURG_IMPUTE : null;
}

// Recalcule piliers + score + rang pour un tableau de villes (modifié ou non).
export function recompute(cities, w = W_DEFAUT) {
  const prix = cities.map(prixEffectif);
  const effort = cities.map((c) => (c.taux_effort != null ? c.taux_effort : effortDepuisPrix(prixEffectif(c))));
  const nPrix = minmax(prix, { inverser: true });
  const nEffort = minmax(effort, { inverser: true });
  const nChom = minmax(cities.map((c) => c.taux_chomage), { inverser: true });
  const nCad = minmax(cities.map((c) => c.part_cadres));
  const nPi = minmax(cities.map((c) => c.part_prof_interm));
  const nDens = minmax(cities.map((c) => c.densite_etudiante));
  const n1524 = minmax(cities.map((c) => c.part_15_24));
  const nDipl = minmax(cities.map((c) => c.part_diplomes_sup));
  const nEtu = minmax(cities.map((c) => c.effectifs));

  const scored = cities.map((c, i) => ({
    ...c,
    pilier_logement: Math.round((0.7 * nPrix[i] + 0.3 * nEffort[i]) * 10) / 10,
    pilier_emploi: Math.round((0.5 * nChom[i] + 0.3 * nCad[i] + 0.2 * nPi[i]) * 10) / 10,
    pilier_demographie: Math.round((0.6 * nDens[i] + 0.4 * n1524[i]) * 10) / 10,
    pilier_formation: Math.round((0.7 * nEtu[i] + 0.3 * nDipl[i]) * 10) / 10,
  }));
  for (const s of scored) {
    s.score_calc =
      Math.round(
        (w.logement * s.pilier_logement +
          w.emploi * s.pilier_emploi +
          w.demographie * s.pilier_demographie +
          w.formation * s.pilier_formation) *
          10,
      ) / 10;
  }
  const order = [...scored].sort((a, b) => b.score_calc - a.score_calc);
  order.forEach((s, i) => (s.rang_calc = i + 1));
  return order;
}

// Score pondéré direct depuis les piliers stockés (classement à curseurs).
export function scoreAvecPoids(c, w) {
  const tot = w.logement + w.emploi + w.demographie + w.formation;
  const p = (k) => w[k] / tot;
  return (
    Math.round(
      (p("logement") * c.score_logement +
        p("emploi") * c.score_emploi +
        p("demographie") * c.score_demographie +
        p("formation") * c.score_formation) *
        10,
    ) / 10
  );
}

// Haversine — distance géodésique en km.
export function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const toRad = (d) => (d * Math.PI) / 180;
  const dp = toRad(lat2 - lat1);
  const dl = toRad(lon2 - lon1);
  const a =
    Math.sin(dp / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// Garde-fous de vraisemblance (non bloquants) — identiques à simulateur.py.
export function gardeFous(scenario) {
  const a = [];
  if (Math.abs(scenario.prixPct) > 30) a.push("Variation de prix supérieure à 30 % : scénario extrême, à lire comme une exploration.");
  if (scenario.chomagePts && (scenario.chomagePts < 0 || scenario.chomagePts > 0)) {
    const apres = scenario.ville.taux_chomage + scenario.chomagePts;
    if (apres < 3 || apres > 30) a.push(`Taux de chômage simulé à ${apres.toFixed(1)} % : hors du range plausible des 20 villes (3–30 %).`);
  }
  if (scenario.etudiants && Math.abs(scenario.etudiants) > 0.5 * scenario.ville.effectifs)
    a.push("Variation d'effectifs supérieure à ±50 % du stock actuel : très peu réaliste à court terme.");
  if (scenario.part1524 && scenario.ville.part_15_24 + scenario.part1524 > 40)
    a.push("Part des 15-24 ans au-dessus de 40 % : aucune ville du panel n'atteint ce niveau.");
  if (scenario.diplSup && scenario.ville.part_diplomes_sup + scenario.diplSup > 80)
    a.push("Part de diplômés du supérieur au-dessus de 80 % : niveau jamais observé dans le panel.");
  return a;
}

export function scoreColor(s) {
  if (s >= 60) return "#2ea66f";
  if (s >= 50) return "#e0a83e";
  if (s >= 45) return "#e58a4e";
  return "#ef6351";
}
