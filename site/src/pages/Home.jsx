import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getData } from "../lib/data.js";
import { tr, fmtNum, fmtInt } from "../lib/i18n.js";
import { useLang } from "../App.jsx";
import MapFrance from "../components/MapFrance.jsx";
import { ScoreBar } from "../components/bits.jsx";
import { scoreColor } from "../lib/scoring.js";

export default function Home() {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  const navigate = useNavigate();
  useEffect(() => { getData().then(setData); }, []);

  if (!data) return <p className="loading">Chargement…</p>;
  const { cities, panel, meta } = data;
  const top5 = cities.slice(0, 5);
  const aix = cities.find((c) => c.slug === "aix-en-provence");
  const strasbourg = cities.find((c) => c.slug === "strasbourg");

  return (
    <div className="home">
      <section className="hero">
        <p className="kicker">{tr(lang, "hero_kicker")}</p>
        <h1>{tr(lang, "hero_title")}</h1>
        <p className="hero-sub">{tr(lang, "hero_sub")}</p>
        <p className="hero-finding">
          Le fait marquant des données : <b>Aix-en-Provence</b> envoie plus d'étudiants qu'elle n'en accueille
          ({aix.ratio_attractivite} entrée pour une sortie), retient le moins bien ses jeunes diplômés
          ({aix.taux_ancrage} %)… et attire pourtant le plus d'arrivées du panel
          ({aix.arrivees_relatives} % par an). Éduquer n'est pas retenir, et retenir n'est pas attirer.
        </p>
        <div className="hero-ctas">
          <Link to="/quiz" className="btn primary">{tr(lang, "cta_quiz")}</Link>
          <a href="#carte" className="btn">{tr(lang, "cta_carte")}</a>
        </div>
      </section>

      <section id="carte" className="section">
        <h2>{tr(lang, "trouver_ville")}</h2>
        <p className="section-sub">
          {cities.length} villes universitaires, couleur = score global, clic = fiche complète. Données :{" "}
          {meta.sources[0].split(" : ")[0].toLowerCase()}, INSEE RP 2023, DVF 2025.
        </p>
        <MapFrance cities={cities} lang={lang} />
      </section>

      <section className="section two-col">
        <div>
          <h2>{tr(lang, "top5")}</h2>
          <ol className="top5">
            {top5.map((c) => (
              <li key={c.slug}>
                <button className="top5-row" onClick={() => navigate(`/ville/${c.slug}`)}>
                  <span className="rank">#{c.rang}</span>
                  <span className="name">{c.nom}</span>
                  <span className="score" style={{ color: scoreColor(c.score_global) }}>{fmtNum(c.score_global)}</span>
                  <ScoreBar value={c.score_global} />
                </button>
              </li>
            ))}
          </ol>
          <Link to="/classement" className="btn small">{tr(lang, "toutes_villes")} →</Link>
        </div>
        <div className="mobility-box">
          <h2>{tr(lang, "mobilite_titre")}</h2>
          <p>{tr(lang, "mobilite_texte")}</p>
          <div className="mob-compare">
            <div className="mob-card">
              <h3>Aix-en-Provence</h3>
              <p className="mob-kpi">{aix.taux_ancrage} % <small>{tr(lang, "ancrage")}</small></p>
              <p className="mob-kpi hot">{aix.arrivees_relatives} % <small>{tr(lang, "arrivees")}</small></p>
              <p className="mob-note">Attire fortement malgré une retenue faible.</p>
            </div>
            <div className="mob-card">
              <h3>Strasbourg</h3>
              <p className="mob-kpi">{strasbourg.taux_ancrage} % <small>{tr(lang, "ancrage")}</small></p>
              <p className="mob-kpi">{strasbourg.arrivees_relatives} % <small>{tr(lang, "arrivees")}</small></p>
              <p className="mob-note">Retient le mieux, attire le moins de diplômés.</p>
            </div>
          </div>
          <Link to="/articles/ou-rester-apres-etudes" className="btn small">{tr(lang, "lire_article")} →</Link>
        </div>
      </section>
    </div>
  );
}
