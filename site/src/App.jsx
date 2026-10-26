import React, { createContext, useContext, useState, useEffect } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
import { tr, LANGS } from "./lib/i18n.js";

const LangCtx = createContext({ lang: "fr", setLang: () => {} });
export const useLang = () => useContext(LangCtx);

export default function App() {
  const [lang, setLang] = useState(localStorage.getItem("lang") || "fr");
  useEffect(() => { localStorage.setItem("lang", lang); }, [lang]);
  const loc = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [loc.pathname]);

  const nav = [
    ["/", "nav_accueil"],
    ["/classement", "nav_classement"],
    ["/quiz", "nav_quiz"],
    ["/simulateur", "nav_simulateur"],
    ["/articles", "nav_articles"],
    ["/demarche", "nav_demarche"],
  ];

  return (
    <LangCtx.Provider value={{ lang, setLang }}>
      <div className="app">
        <header className="nav">
          <NavLink to="/" className="brand">
            Edu<span>Move</span>
          </NavLink>
          <nav className="nav-links">
            {nav.map(([to, key]) => (
              <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "on" : "")}>
                {tr(lang, key)}
              </NavLink>
            ))}
          </nav>
          <select
            className="lang-select"
            aria-label="Langue"
            value={lang}
            onChange={(e) => setLang(e.target.value)}
          >
            {Object.entries(LANGS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </header>
        <main>
          <Outlet />
        </main>
        <footer className="footer">
          <div>
            <p className="footer-brand">EduMove — Atlas de l'attractivité étudiante</p>
            <p className="footer-note">
              {tr(lang, "footer_github")} :{" "}
              <a href="https://github.com/samz86/edu-move" target="_blank" rel="noreferrer">
                github.com/samz86/edu-move
              </a>
            </p>
            <p className="footer-note">
              {tr(lang, "disclaimer")} · {tr(lang, "maj")} : 17/10/2026
            </p>
          </div>
        </footer>
      </div>
    </LangCtx.Provider>
  );
}
