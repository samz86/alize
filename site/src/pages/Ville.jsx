import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getData, ficheVille } from "../lib/data.js";
import { tr, fmtNum, fmtInt } from "../lib/i18n.js";
import { useLang } from "../App.jsx";
import Markdown from "../components/Markdown.jsx";
import { PillarCard, Radar, DistBars, Kpi } from "../components/bits.jsx";
import { scoreColor } from "../lib/scoring.js";

// Page ville : dashboard (score, piliers, radar vs panel, distributions,
// formations Parcoursup, voisines) + fiche intégrale (contenu éditorial
// sourcé) dessous.
export default function Ville() {
  const { slug } = useParams();
  const { lang } = useLang();
  const [data, setData] = useState(null);
  useEffect(() => { getData().then(setData); }, []);
  if (!data) return <p className="loading">Chargement…</p>;

  const { cities, panel, formations } = data;
  const c = cities.find((x) => x.slug === slug);
  if (!c) return <p className="loading">Ville introuvable.</p>;
  const fiche = ficheVille(slug);
  const f = formations && formations[slug];
  const idx = cities.findIndex((x) => x.slug === slug);
  const voisines = [cities[idx - 1], cities[idx + 1]].filter(Boolean);

  const pillars = [c.score_logement, c.score_emploi, c.score_demographie, c.score_formation];
  const moys = [
    panel.score_logement.moy,
    panel.score_emploi.moy,
    panel.score_demographie.moy,
    panel.score_formation.moy,
  ];
  const labels = [tr(lang, "logement"), tr(lang, "emploi"), tr(lang, "demographie"), tr(lang, "formation")];
  const weights = { logement: 0.3, emploi: 0.25, demographie: 0.25, formation: 0.2 };

  return (
    <div className="page ville">
      <header className="ville-head">
        <div>
          <p className="kicker">{c.rang}
            <sup>e</sup> / {cities.length} · {tr(lang, "score")}{" "}
            <b style={{ color: scoreColor(c.score_global) }}>{fmtNum(c.score_global)}</b>/100
            {c.risque && <span className={`risk risk-${c.risque}`}>Risque de pari : {c.risque}</span>}
          </p>
          <h1>{c.nom}</h1>
          <p className="ville-intro">{c.intro}</p>
        </div>
      </header>

      <section className="pillar-grid">
        <PillarCard label={tr(lang, "logement")} poids={weights.logement} value={c.score_logement} moy={moys[0]} lang={lang} />
        <PillarCard label={tr(lang, "emploi")} poids={weights.emploi} value={c.score_emploi} moy={moys[1]} lang={lang} />
        <PillarCard label={tr(lang, "demographie")} poids={weights.demographie} value={c.score_demographie} moy={moys[2]} lang={lang} />
        <PillarCard label={tr(lang, "formation")} poids={weights.formation} value={c.score_formation} moy={moys[3]} lang={lang} />
      </section>

      <section className="dash">
        <div className="dash-card">
          <h3>{c.nom} {tr(lang, "vs_panel")}</h3>
          <Radar pillars={pillars} moyennes={moys} labels={labels} />
        </div>
        <div className="dash-card">
          <h3>Indicateurs clés</h3>
          <div className="kpis">
            <Kpi label={tr(lang, "prix")} value={c.prix_m2 != null ? fmtInt(c.prix_m2) + " €" : "n.d."} rang={c.prix_impute ? "droit local" : null} />
            <Kpi label={tr(lang, "chomage")} value={fmtNum(c.taux_chomage) + " %"} />
            <Kpi label={tr(lang, "etudiants_kpi")} value={fmtInt(c.effectifs)} />
            <Kpi label="Densité étudiante" value={fmtNum(c.densite_etudiante) + " %"} />
            <Kpi label="Part 15-24 ans" value={fmtNum(c.part_15_24) + " %"} />
            <Kpi label="Part diplômés sup." value={fmtNum(c.part_diplomes_sup) + " %"} />
            {c.taux_ancrage != null && <Kpi label={tr(lang, "ancrage")} value={fmtNum(c.taux_ancrage) + " %"} />}
            {c.arrivees_relatives != null && <Kpi label={tr(lang, "arrivees")} value={fmtNum(c.arrivees_relatives) + " %"} />}
          </div>
          <p className="dash-note">{c.dynamique && <>Dynamique des arrivées de diplômés : <b>{c.dynamique}</b>.</>}</p>
        </div>
        <div className="dash-card">
          <h3>{tr(lang, "score")} — distribution des {cities.length} villes</h3>
          <DistBars cities={cities} valueKey="score_global" activeSlug={slug} fmt={(v) => fmtNum(v)} />
        </div>
      </section>

      <section className="formations">
        <h3>{tr(lang, "formations_titre")}</h3>
        {f ? (
          <>
            <div className="kpis">
              <Kpi label={tr(lang, "formations_kpi")} value={fmtInt(f.nb_formations)} />
              <Kpi label={tr(lang, "formations_etabs")} value={fmtInt(f.nb_etablissements)} />
              <Kpi label={tr(lang, "formations_familles")} value={fmtInt(f.familles_presentes)} />
              <Kpi label={tr(lang, "formations_apprentissage")} value={f.part_apprentissage != null ? fmtNum(f.part_apprentissage) + " %" : "n.d."} />
            </div>
            {Array.isArray(f.familles) && f.familles.length > 0 && (
              <div className="fam-chips">
                {f.familles.slice(0, 10).map((x) => (
                  <span key={x.famille} className="chip">
                    {x.famille} <b>{x.nb}</b>
                  </span>
                ))}
              </div>
            )}
            <p className="dash-note">{tr(lang, "parcoursup_note")}</p>
          </>
        ) : (
          <p className="dash-note">À venir.</p>
        )}
      </section>

      <section className="voisines">
        <h3>{tr(lang, "prochaine_ville")}</h3>
        <div className="voisines-row">
          {voisines.map((v) => (
            <Link key={v.slug} to={`/ville/${v.slug}`} className="voisine-card">
              <b>{v.nom}</b>
              <span>{v.rang}
                <sup>e</sup> · {fmtNum(v.score_global)}/100</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="fiche">
        <h2>Fiche complète — {c.nom}</h2>
        {fiche ? <Markdown source={fiche} /> : <p>À venir.</p>}
      </section>
    </div>
  );
}