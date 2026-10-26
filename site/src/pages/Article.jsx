import React from "react";
import { Link, useParams } from "react-router-dom";
import { contenuArticle, titreArticle, listeArticles } from "../lib/data.js";
import Markdown from "../components/Markdown.jsx";

export default function Article() {
  const { slug } = useParams();
  const source = contenuArticle(slug);
  const autres = listeArticles.filter((a) => a.slug !== slug).slice(0, 3);
  return (
    <div className="page article-page">
      <Link to="/articles" className="crumb">← Analyses</Link>
      <h1>{titreArticle(slug)}</h1>
      {source ? <Markdown source={source} /> : <p>À venir.</p>}
      <div className="autres">
        <h3>À lire aussi</h3>
        {autres.map((a) => (
          <Link key={a.slug} to={`/articles/${a.slug}`} className="autre-link">
            {titreArticle(a.slug)}
          </Link>
        ))}
      </div>
    </div>
  );
}
