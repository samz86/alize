import React from "react";
import { scoreColor } from "../lib/scoring.js";
import { tr } from "../lib/i18n.js";

export function ScoreBar({ value, max = 100 }) {
  return (
    <div className="score-bar" aria-label={`${value}/100`}>
      <div className="score-bar-fill" style={{ width: `${(value / max) * 100}%`, background: scoreColor(value) }} />
    </div>
  );
}

export function PillarCard({ label, poids, value, moy, lang }) {
  return (
    <div className="pillar-card">
      <div className="pillar-head">
        <span className="pillar-name">{label}</span>
        <span className="pillar-weight">{tr(lang, "poids")} {Math.round(poids * 100)} %</span>
      </div>
      <div className="pillar-score">
        <span className="big" style={{ color: scoreColor(value) }}>{value}</span>
        <span className="sub">/100</span>
      </div>
      <ScoreBar value={value} />
      <p className="pillar-moy">{tr(lang, "moyenne_panel")} : {moy.toFixed(1)}</p>
    </div>
  );
}

// Radar SVG — ville (ambre) vs moyenne du panel (gris pointillé), 4 axes.
export function Radar({ pillars, moyennes, labels, size = 240 }) {
  const cx = size / 2, cy = size / 2, R = size / 2 - 34;
  const axes = labels.map((l, i) => {
    const a = (Math.PI * 2 * i) / labels.length - Math.PI / 2;
    return { a, l, x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  const poly = (vals) =>
    axes.map((ax, i) => [cx + (R * vals[i]) / 100 * Math.cos(ax.a), cy + (R * vals[i]) / 100 * Math.sin(ax.a)].join(",")).join(" ");
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="radar" role="img" aria-label="Radar : ville vs moyenne des 20 villes">
      {[25, 50, 75, 100].map((g) => (
        <circle key={g} cx={cx} cy={cy} r={(R * g) / 100} className="radar-grid" />
      ))}
      {axes.map((ax) => (
        <line key={ax.l} x1={cx} y1={cy} x2={ax.x} y2={ax.y} className="radar-grid" />
      ))}
      <polygon points={poly(moyennes)} className="radar-moy" />
      <polygon points={poly(pillars)} className="radar-city" />
      {axes.map((ax) => (
        <text key={ax.l} x={cx + (R + 18) * Math.cos(ax.a)} y={cy + (R + 18) * Math.sin(ax.a) + 4} className="radar-label">
          {ax.l}
        </text>
      ))}
    </svg>
  );
}

// Barres horizontales : une valeur par ville, la ville active en surbrillance.
export function DistBars({ cities, valueKey, activeSlug, fmt }) {
  const sorted = [...cities].sort((a, b) => (b[valueKey] ?? -1) - (a[valueKey] ?? -1));
  const max = Math.max(...cities.map((c) => c[valueKey]).filter((v) => v != null));
  return (
    <div className="dist">
      {sorted.map((c) => (
        <div key={c.slug} className={`dist-row ${c.slug === activeSlug ? "on" : ""}`}>
          <span className="dist-name">{c.nom}</span>
          <span className="dist-track">
            <span className="dist-fill" style={{ width: `${((c[valueKey] ?? 0) / max) * 100}%` }} />
          </span>
          <span className="dist-val">{fmt(c[valueKey])}</span>
        </div>
      ))}
    </div>
  );
}

export function Kpi({ label, value, unit, rang }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">
        {value}
        {unit && <small> {unit}</small>}
      </span>
      {rang && <span className="kpi-rang">{rang}</span>}
    </div>
  );
}
