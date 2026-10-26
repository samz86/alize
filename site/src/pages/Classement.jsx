import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getData } from "../lib/data.js";
import { tr, fmtNum } from "../lib/i18n.js";
import { useLang } from "../App.jsx";
import { scoreAvecPoids, W_DEFAUT, scoreColor } from "../lib/scoring.js";

// Classement triable + curseurs de pondération : le reclassement est
// recalculé en direct depuis les piliers stockés (aucun chiffre en dur).
export default function Classement() {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  const [w, setW] = useState({ logement: 30, emploi: 25, demographie: 25, formation: 20 });
  const [sortKey, setSortKey] = useState(null);
  const navigate = useNavigate();
  useEffect(() => { getData().then(setData); }, []);
  if (!data) return <p className="loading">Chargement…</p>;

  const { cities } = data;
  const ranked = [...cities]
    .map((c) => ({ ...c, score_w: scoreAvecPoids(c, w) }))
    .sort((a, b) => b.score_w - a.score_w);
  const shown = sortKey
    ? [...ranked].sort((a, b) => (b[sortKey] ?? -1) - (a[sortKey] ?? -1))
    : ranked;
  const total = w.logement + w.emploi + w.demographie + w.formation;
  const reset = () => setW({ logement: 30, emploi: 25, demographie: 25, formation: 20 });

  const P = [
    ["logement", "logement", 30],
    ["emploi", "emploi", 25],
    ["demographie", "demographie", 25],
    ["formation", "formation", 20],
  ];

  return (
    <div className="page classement">
      <h1>{tr(lang, "nav_classement")}</h1>
      <p className="page-sub">
        {tr(lang, "disclaimer")} Piliers : min-max 0-100 sur le panel, pondération de départ 30/25/25/20.
      </p>

      <div className="sliders">
        {P.map(([key, label, def]) => (
          <label key={key} className="slider">
            <span>
              {tr(lang, label)} <b>{Math.round((w[key] / total) * 100)} %</b>
            </span>
            <input
              type="range"
              min="0"
              max="50"
              step="5"
              value={w[key]}
              aria-label={`Poids ${tr(lang, label)}`}
              onChange={(e) => setW({ ...w, [key]: +e.target.value })}
            />
          </label>
        ))}
        <button className="btn small ghost" onClick={reset}>Réinitialiser</button>
      </div>

      <table className="classement-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Ville</th>
            <th>{tr(lang, "score")}</th>
            <th className="th-sort" onClick={() => setSortKey(sortKey === "score_logement" ? null : "score_logement")}>{tr(lang, "logement")}</th>
            <th className="th-sort" onClick={() => setSortKey(sortKey === "score_emploi" ? null : "score_emploi")}>{tr(lang, "emploi")}</th>
            <th className="th-sort" onClick={() => setSortKey(sortKey === "score_demographie" ? null : "score_demographie")}>{tr(lang, "demographie")}</th>
            <th className="th-sort" onClick={() => setSortKey(sortKey === "score_formation" ? null : "score_formation")}>{tr(lang, "formation")}</th>
            <th className="th-sort" onClick={() => setSortKey(sortKey === "taux_ancrage" ? null : "taux_ancrage")}>{tr(lang, "ancrage")}</th>
            <th className="th-sort" onClick={() => setSortKey(sortKey === "arrivees_relatives" ? null : "arrivees_relatives")}>{tr(lang, "arrivees")}</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((c, i) => (
            <tr key={c.slug} className="row-link" onClick={() => navigate(`/ville/${c.slug}`)}>
              <td>{i + 1}</td>
              <td className="city-cell">{c.nom}{c.prix_impute && <sup title="Prix DVF indisponible : imputé pour le score">†</sup>}</td>
              <td>
                <b style={{ color: scoreColor(c.score_w) }}>{fmtNum(c.score_w)}</b>
              </td>
              <td>{fmtNum(c.score_logement)}</td>
              <td>{fmtNum(c.score_emploi)}</td>
              <td>{fmtNum(c.score_demographie)}</td>
              <td>{fmtNum(c.score_formation)}</td>
              <td>{c.taux_ancrage != null ? fmtNum(c.taux_ancrage) + " %" : "à venir"}</td>
              <td>{c.arrivees_relatives != null ? fmtNum(c.arrivees_relatives) + " %" : "à venir"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="foot-note">
        † Strasbourg : prix immobilier indisponible (droit local Alsace-Moselle), imputé à la médiane du panel pour le score uniquement.
        Poids affichés : {Math.round((w.logement / total) * 100)}/{Math.round((w.emploi / total) * 100)}/
        {Math.round((w.demographie / total) * 100)}/{Math.round((w.formation / total) * 100)} (normalisés à 100).
      </p>
      <p>
        <a className="btn small ghost" href={`${import.meta.env.BASE_URL}data/villes_scoring.csv`} download>
          {tr(lang, "download_csv")}
        </a>
      </p>
    </div>
  );
}
