import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getData } from "../lib/data.js";
import { tr, fmtNum } from "../lib/i18n.js";
import { useLang } from "../App.jsx";
import { scoreAvecPoids, haversine } from "../lib/scoring.js";

// ---------------------------------------------------------------------
// Quiz « Quelle ville est faite pour toi ? » — portage fidèle de
// transform/quiz.py (question 0 commune via API Géo + 7 questions A/B/C,
// ajustements de poids sur la base 30/25/25/20, filtre 300 km si « rester
// proche », transparence totale sur la pondération).
// ---------------------------------------------------------------------

const W_BASE = { logement: 30, emploi: 25, demographie: 25, formation: 20 };

const QUESTIONS = [
  {
    cle: "budget",
    q: "1. Côté argent, ta situation plutôt… ?",
    choix: {
      A: ["Serrée : je compte chaque euro", { logement: 15 }],
      B: ["Ça va, mais je dois faire attention", { logement: 5, formation: 5 }],
      C: ["Tranquille : je veux surtout profiter de la ville", { formation: 5, demographie: 5 }],
    },
  },
  {
    cle: "ville",
    q: "2. Tu préfères vivre dans quelle ville ?",
    choix: {
      A: ["Une petite ou moyenne ville : on va partout à pied ou à vélo", { demographie: 10 }],
      B: ["Une grande ville : beaucoup de choses à faire et de monde", { formation: 10 }],
      C: ["Les deux me vont, l'important c'est que le campus soit vivant", { demographie: 5, formation: 5 }],
    },
  },
  {
    cle: "apres",
    q: "3. Après ton diplôme, tu penses faire quoi ?",
    choix: {
      A: ["Rester dans la ville où j'ai étudié et y travailler", { emploi: 10 }],
      B: ["Partir là où je trouverai le meilleur travail", { emploi: 5, formation: 5 }],
      C: ["Je ne sais pas encore, on verra", {}],
    },
  },
  {
    cle: "soirees",
    q: "4. À côté des cours, tu cherches quoi ?",
    choix: {
      A: ["De l'ambiance : associations, sorties, vie étudiante à fond", { demographie: 10 }],
      B: ["Du calme : bien étudier dans un cadre agréable", { logement: 10 }],
      C: ["Un mélange des deux", { demographie: 5, logement: 5 }],
    },
  },
  {
    cle: "trajet",
    q: "5. Trouver un job ou une alternance pendant tes études, pour toi c'est… ?",
    choix: {
      A: ["Très important : je veux en trouver facilement sur place", { emploi: 15 }],
      B: ["Pas nécessaire : je me concentre sur mes études", { formation: 10 }],
      C: ["Sympa si possible, mais pas indispensable", { emploi: 5 }],
    },
  },
  {
    cle: "logement",
    q: "6. Pour toi, le logement idéal c'est… ?",
    choix: {
      A: ["Pas cher avant tout : un studio simple me suffit", { logement: 10 }],
      B: ["Confortable : j'aime avoir un vrai chez-moi agréable", { logement: 5, emploi: 5 }],
      C: ["Facile à trouver : je déteste galérer dans les recherches", { logement: 5, demographie: 5 }],
    },
  },
  {
    cle: "region",
    q: "7. Loin de chez toi, ça te dit quoi ?",
    choix: {
      A: ["Super : je veux découvrir une nouvelle région", { formation: 10 }],
      B: ["Bof : je préfère rester pas trop loin de ma famille", { logement: 5, demographie: 5 }],
      C: ["Peu importe la distance, je choisis pour mes études", { formation: 5, emploi: 5 }],
    },
  },
];

async function geolocaliser(nom) {
  // API Géo (api.gouv.fr, sans clé) — jamais bloquante : si injoignable,
  // le quiz continue sans filtre de proximité.
  try {
    const r = await fetch(
      `https://geo.api.gouv.fr/communes?nom=${encodeURIComponent(nom)}&fields=centre&boost=population`
    ).then((x) => x.json());
    if (!r.length || !r[0].centre) return null;
    const [lon, lat] = r[0].centre.coordinates; // GeoJSON : [lon, lat]
    return { lat, lon, nom: r[0].nom };
  } catch {
    return null;
  }
}

export default function Quiz() {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  const [step, setStep] = useState(0); // 0 = commune, 1..7 = questions, 8 = résultat
  const [commune, setCommune] = useState("");
  const [geo, setGeo] = useState(null);
  const [geoNote, setGeoNote] = useState("");
  const [rep, setRep] = useState({});
  const [result, setResult] = useState(null);

  useEffect(() => { getData().then(setData); }, []);

  async function validerCommune() {
    const g = commune.trim() ? await geolocaliser(commune.trim()) : null;
    setGeo(g);
    setGeoNote(commune.trim() ? (g ? `Commune reconnue : ${g.nom}.` : "Commune non reconnue : le quiz reste valable, filtre de proximité désactivé.") : "");
    setStep(1);
  }

  function repondre(cle, lettre) {
    const r = { ...rep, [cle]: lettre };
    setRep(r);
    if (step === 7) {
      // calcule le résultat
      const w = { ...W_BASE };
      let ajouts = 0;
      for (const q of QUESTIONS) {
        const l = r[q.cle];
        if (l && q.choix[l]) {
          for (const [p, pts] of Object.entries(q.choix[l][1])) {
            w[p] += pts;
            ajouts += pts;
          }
        }
      }
      const total = Object.values(w).reduce((a, b) => a + b, 0);
      const poids = Object.fromEntries(Object.entries(w).map(([k, v]) => [k, v / total]));
      const scored = data.cities
        .map((c) => ({ ...c, score_quiz: scoreAvecPoids(c, { logement: w.logement, emploi: w.emploi, demographie: w.demographie, formation: w.formation }) }))
        .sort((a, b) => b.score_quiz - a.score_quiz);
      let top = scored;
      let filtre = false;
      if (geo && r.region === "B") {
        const dans = scored.filter((c) => haversine(geo.lat, geo.lon, c.lat, c.lon) <= 300);
        if (dans.length >= 3) { top = dans; filtre = true; }
      }
      setResult({ poids, w, ajouts, top: top.slice(0, 5), bottom: [...top].slice(-3), filtre, geo });
    }
    setStep(step + 1);
  }

  if (!data) return <p className="loading">Chargement…</p>;

  if (step === 0) {
    return (
      <div className="page quiz">
        <h1>{tr(lang, "nav_quiz")}</h1>
        <p className="page-sub">
          8 étapes, aucune bonne réponse : seulement tes priorités. Chaque réponse ajuste la pondération
          des 4 piliers (départ 30/25/25/20).
        </p>
        <div className="quiz-box">
          <h3>0. Ta commune de départ ?</h3>
          <p className="quiz-note">Sert uniquement à afficher les distances. Champ facultatif.</p>
          <input
            value={commune}
            onChange={(e) => setCommune(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && validerCommune()}
            placeholder="ex. Melun, Gagny, Montry…"
            aria-label="Commune de domicile"
          />
          {geoNote && <p className="quiz-note">{geoNote}</p>}
          <button className="btn primary" onClick={validerCommune}>Continuer</button>
        </div>
      </div>
    );
  }

  if (step <= 7) {
    const q = QUESTIONS[step - 1];
    return (
      <div className="page quiz">
        <h1>{tr(lang, "nav_quiz")}</h1>
        <div className="quiz-progress">
          {QUESTIONS.map((_, i) => (
            <span key={i} className={i < step ? "dot on" : "dot"} />
          ))}
        </div>
        <div className="quiz-box">
          <h3>{q.q}</h3>
          <div className="quiz-choix">
            {Object.entries(q.choix).map(([l, [txt, pts]]) => (
              <button key={l} className="choix" onClick={() => repondre(q.cle, l)}>
                <b>{l}.</b> {txt}
              </button>
            ))}
          </div>
          <button className="btn small ghost" onClick={() => repondre(q.cle, null)}>Passer (neutre)</button>
        </div>
      </div>
    );
  }

  const { poids, w, top, bottom, filtre } = result;
  return (
    <div className="page quiz">
      <h1>Tes villes, selon tes priorités</h1>
      <p className="page-sub">{tr(lang, "quiz_disclaimer")}</p>
      <div className="quiz-result">
        <div className="poids-box">
          <h3>Ta pondération</h3>
          {Object.entries(poids).map(([k, v]) => (
            <p key={k} className="poids-line">
              {tr(lang, k === "demographie" ? "demographie" : k)} : <b>{Math.round(v * 100)} %</b>
              <span className="defaut">(défaut {Math.round((W_BASE[k] / 100) * 100)} %)</span>
            </p>
          ))}
          <p className="quiz-note">Méthode : piliers min-max 0-100 (INSEE RP 2023, MESR 2025-26, DVF 2025), pondération de départ 30/25/25/20 ajustée par tes réponses.</p>
        </div>
        <ol className="quiz-top">
          {top.map((c, i) => (
            <li key={c.slug}>
              <Link to={`/ville/${c.slug}`} className="quiz-city">
                <span className="rank">#{i + 1}</span>
                <span className="name">{c.nom}</span>
                <span className="score">{fmtNum(c.score_quiz)}</span>
                {result.geo && (
                  <span className="dist">
                    {Math.round(haversine(result.geo.lat, result.geo.lon, c.lat, c.lon))} km
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ol>
        {filtre && <p className="quiz-note">Filtre actif : villes à moins de 300 km de {result.geo.nom}.</p>}
        <p className="quiz-note">
          Moins adaptées à ton profil : {bottom.map((c) => c.nom).join(", ")}.
        </p>
        <button className="btn" onClick={() => { setStep(0); setRep({}); setResult(null); setGeo(null); }}>
          Relancer le quiz
        </button>
      </div>
    </div>
  );
}
