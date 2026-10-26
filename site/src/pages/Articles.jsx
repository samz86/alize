import React from "react";
import { Link } from "react-router-dom";
import { listeArticles, titreArticle } from "../lib/data.js";
import { tr } from "../lib/i18n.js";
import { useLang } from "../App.jsx";

export default function Articles() {
  const { lang } = useLang();
  return (
    <div className="page">
      <h1>{tr(lang, "nav_articles")}</h1>
      <p className="page-sub">
        Chaque chiffre cité vient des données du projet (traçabilité complète). Contextes locaux : presse,
        CROUS, collectivités, observatoires — sources citées dans les textes.
      </p>
      <div className="article-list">
        {listeArticles.map((a) => (
          <Link key={a.slug} to={`/articles/${a.slug}`} className={`article-card ${a.poids ? "featured" : ""}`}>
            <span className="tag">{a.tag}</span>
            {a.poids && <span className="tag sig">Article signature</span>}
            <h2>{titreArticle(a.slug)}</h2>
          </Link>
        ))}
      </div>
    </div>
  );
}
