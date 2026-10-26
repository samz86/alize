import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getData } from "../lib/data.js";
import { tr, fmtNum, fmtInt } from "../lib/i18n.js";
import { useLang } from "../App.jsx";
import { recompute, effortDepuisPrix, gardeFous } from "../lib/scoring.js";

// ---------------------------------------------------------------------
// Simulateur What-if — portage de transform/simulateur.py :
// scénario sur une ville (prix %, chômage pts, effectifs, cadres, 15-24,
// diplômés sup), recalcul min-max du panel, avant/après + top 10,
// garde-fous de vraisemblance non bloquants, disclaimer causalité.
// ---------------------------------------------------------------------

export default function Simulateur() {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  const [ville, setVille] = useState("lyon");
  const [prixPct, setPrixPct] = useState(-10);
  const [chomagePts, setChomagePts] = useState(0);
  const [etudiants, setEtudiants] = useState(0);
  const [partCadres, setPartCadres] = useState(0);

  useEffect(() => { getData().then(setData); }, []);

  const scenario = useMemo(() => {
    if (!data) return null;
    const c = data.cities.find((x) => x.slug === ville);
    return { ville: c, prixPct, chomagePts, etudiants, partCadres };
  }, [data, ville, prixPct, chomagePts, etudiants, partCadres]);

  const out = useMemo(() => {
    if (!data || !scenario) return null;
    const modified = data.cities.map((c) => {
      if (c.slug !== ville) return c;
      const o = { ...c };
      if (prixPct) {
        o.prix_m2 = (c.prix_m2 != null ? c.prix_m2 : 3391.1) * (1 + prixPct / 100);
        o.taux_effort = effortDepuisPrix(o.prix_m2);
      }
      if (chomagePts) o.taux_chomage = Math.max(0, c.taux_chomage + chomagePts);
      if (etudiants) {
        o.effectifs = c.effectifs + etudiants;
        o.densite_etudiante = (100 * o.effectifs) / c.population;
      }
      if (partCadres) o.part_cadres = Math.min(100, Math.max(0, c.part_cadres + partCadres));
      return o;
    });
    const apres = recompute(modified);
    const avant = recompute(data.cities);
    return { avant, apres };
  }, [data, ville, prixPct, chomagePts, etudiants, partCadres]);

  if (!data || !out) return <p className="loading">Chargement…</p>;

  const cAvant = out.avant.find((x) => x.slug === ville);
  const cApres = out.apres.find((x) => x.slug === ville);
  const alertes = gardeFous({ ...scenario, chomagePts: +chomagePts, etudiants: +etudiants });
  const top10 = out.apres.slice(0, 10);

  return (
    <div className="page simulateur">
      <h1>{tr(lang, "simulateur_titre")}</h1>
      <p className="page-sub">{tr(lang, "simu_disclaimer")}</p>

      <div className="sim-controls">
        <label className="sim-field">
          Ville
          <select value={ville} onChange={(e) => setVille(e.target.value)} aria-label="Ville simulée">
            {data.cities.map((c) => (
              <option key={c.slug} value={c.slug}>{c.nom}</option>
            ))}
          </select>
        </label>
        <label className="sim-field">
          Prix m² : <b>{prixPct > 0 ? "+" : ""}{prixPct} %</b>
          <input type="range" min="-50" max="50" step="5" value={prixPct} onChange={(e) => setPrixPct(+e.target.value)} aria-label="Variation du prix en %" />
        </label>
        <label className="sim-field">
          Chômage : <b>{chomagePts > 0 ? "+" : ""}{chomagePts} pt(s)</b>
          <input type="range" min="-4" max="4" step="0.5" value={chomagePts} onChange={(e) => setChomagePts(+e.target.value)} aria-label="Variation du chômage en points" />
        </label>
        <label className="sim-field">
          Effectifs : <b>{etudiants > 0 ? "+" : ""}{etudiants}</b>
          <input type="range" min="-10000" max="10000" step="1000" value={etudiants} onChange={(e) => setEtudiants(+e.target.value)} aria-label="Variation des effectifs" />
        </label>
        <label className="sim-field">
          Part de cadres : <b>{partCadres > 0 ? "+" : ""}{partCadres} pt(s)</b>
          <input type="range" min="-5" max="5" step="1" value={partCadres} onChange={(e) => setPartCadres(+e.target.value)} aria-label="Variation de la part de cadres" />
        </label>
      </div>

      {alertes.length > 0 && (
        <ul className="gardefous">
          {alertes.map((a) => <li key={a}>⚠ {a}</li>)}
        </ul>
      )}

      <div className="sim-apres">
        <h3>{cApres.nom} — {tr(lang, "avant")} → {tr(lang, "apres")}</h3>
        <table className="classement-table small">
          <thead>
            <tr><th>{tr(lang, "score")}</th><th>{tr(lang, "rang_kpi")}</th><th>{tr(lang, "logement")}</th><th>{tr(lang, "emploi")}</th><th>{tr(lang, "demographie")}</th><th>{tr(lang, "formation")}</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><b>{fmtNum(cAvant.score_calc)}</b> → <b className="hot">{fmtNum(cApres.score_calc)}</b></td>
              <td>{cAvant.rang_calc}
                <sup>e</sup> → <b className="hot">{cApres.rang_calc}
                  <sup>e</sup></b></td>
              <td>{fmtNum(cAvant.pilier_logement)} → {fmtNum(cApres.pilier_logement)}</td>
              <td>{fmtNum(cAvant.pilier_emploi)} → {fmtNum(cApres.pilier_emploi)}</td>
              <td>{fmtNum(cAvant.pilier_demographie)} → {fmtNum(cApres.pilier_demographie)}</td>
              <td>{fmtNum(cAvant.pilier_formation)} → {fmtNum(cApres.pilier_formation)}</td>
            </tr>
          </tbody>
        </table>
        <p className="foot-note">
          Prix simulé : {fmtInt(cApres.prix_m2)} €/m² · taux d'effort recalculé : {fmtNum(cApres.taux_effort)} %
          {cAvant.slug === "strasbourg" && " (Strasbourg : prix de départ imputé, droit local)"}
        </p>
      </div>

      <div className="sim-top10">
        <h3>Top 10 recalculé</h3>
        <table className="classement-table small">
          <tbody>
            {top10.map((c, i) => (
              <tr key={c.slug} className={c.slug === ville ? "row-hot" : ""}>
                <td>{i + 1}</td>
                <td><Link to={`/ville/${c.slug}`}>{c.nom}</Link></td>
                <td>{fmtNum(c.score_calc)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="foot-note">
        Les scores restent relatifs au panel : un scénario sur une ville déplace aussi, par construction,
        la normalisation des 19 autres. Voir <Link to="/demarche">la démarche</Link>.
      </p>
    </div>
  );
}
