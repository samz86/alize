import React, { useEffect, useState } from "react";
import { getData } from "../lib/data.js";
import { tr } from "../lib/i18n.js";
import { useLang } from "../App.jsx";

// La démarche : transparence méthodologique — sources, formule du score,
// robustesse, limites assumées, reproductibilité. Argument central pour
// un jury ou un recruteur : chaque choix est défendable.
export default function Demarche() {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  useEffect(() => { getData().then(setData); }, []);
  if (!data) return <p className="loading">Chargement…</p>;
  const { meta } = data;

  return (
    <div className="page demarche">
      <h1>{tr(lang, "nav_demarche")}</h1>
      <p className="page-sub">
        Un projet data n'est créditable que s'il est reproductible et s'il assume ses limites.
        Cette page documente chaque choix méthodologique.
      </p>

      <section>
        <h2>1. Les sources</h2>
        <ul className="sources">
          {meta.sources.map((s) => <li key={s}>{s}</li>)}
        </ul>
        <p>Toutes les sources sont ouvertes et gratuites. Aucune donnée n'est achetée, aucune clé n'est embarquée dans le site.</p>
      </section>

      <section>
        <h2>2. Le score</h2>
        <p>
          Chaque indicateur est normalisé min-max de 0 à 100 sur le panel des 20 villes (prix et chômage
          inversés : bas = meilleur). Les piliers combinent les indicateurs :
        </p>
        <ul>
          <li><b>Logement (30 %)</b> : 0,7 × prix médian du m² + 0,3 × taux d'effort (studio 20 m², budget 800 €/mois, loyer ≈ 0,5 % de la valeur d'achat par mois).</li>
          <li><b>Emploi (25 %)</b> : 0,5 × chômage (inversé) + 0,3 × part de cadres + 0,2 × professions intermédiaires.</li>
          <li><b>Démographie (25 %)</b> : 0,6 × densité étudiante + 0,4 × part des 15-24 ans.</li>
          <li><b>Formation (20 %)</b> : 0,7 × effectifs d'étudiants + 0,3 × part de diplômés du supérieur.</li>
        </ul>
        <p>
          Le taux d'effort est une transformation affine du prix (prix ÷ 80) : documenté en toute
          transparence, il ne fait qu'expliciter ce que le prix représente pour un budget étudiant type.
        </p>
      </section>

      <section>
        <h2>3. Robustesse du classement</h2>
        <p>
          Six scénarios de pondération ont été rejoués (égalitaire, pro-logement, pro-emploi,
          pro-démographie, pro-formation, pondération de référence). Nancy figure dans le top 5 des
          six scénarios (rang moyen 2,2), Rennes aussi (3,2). Paris ne prend la tête que si la formation
          pèse 50 %. Conclusion : le trio de tête est robuste, le reste du classement dépend des poids —
          d'où le classement à curseurs et le quiz, qui rendent ce choix explicite plutôt que caché.
        </p>
      </section>

      <section>
        <h2>4. Une élasticité testée, non significative</h2>
        <p>
          La régression ln(prix) ~ ln(densité étudiante) + chômage sur les 19 villes (Strasbourg exclu,
          prix imputé) donne R² = 0,38 : le coefficient de densité n'est pas significatif à n = 19
          (IC 95 % contient 0). Seul le chômage l'est (≈ −10 % de prix par point de chômage).
          Le simulateur n'en dérive donc aucune prétention causale.
        </p>
      </section>

      <section>
        <h2>5. {tr(lang, "limites")}</h2>
        <ul>
          {meta.limites.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </section>

      <section>
        <h2>6. Reproductibilité</h2>
        <p>
          Pipeline complet sur GitHub : un script d'extraction par source (src/extract), scores et
          sensibilité (transform/), simulateur et quiz rejouables. Les pièges rencontrés (arrondissements
          de Paris et Lyon dans les fichiers INSEE, jointures de codes communes divergents entre sources,
          prix DVF indisponible en Alsace-Moselle) sont documentés dans le journal de bord du dépôt.
        </p>
        <p>
          <a href="https://github.com/samz86/edu-move" target="_blank" rel="noreferrer">github.com/samz86/edu-move</a>
        </p>
      </section>
    </div>
  );
}
