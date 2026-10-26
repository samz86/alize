import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import regions from "../lib/regions.json";
import { scoreColor } from "../lib/scoring.js";

// ---------------------------------------------------------------------
// Carte de France SVG : contours régionaux simplifiés (découpage antérieur
// à 2016, source ouverte gist Baztoune / IGN) + 20 pastilles villes.
// Couleur = score global. Projection équirectangulaire corrigée latitude.
// ---------------------------------------------------------------------

const W = 760, H = 760;

export default function MapFrance({ cities, lang }) {
  const navigate = useNavigate();
  const [hover, setHover] = useState(null);

  const { path, xy } = useMemo(() => {
    let lo = Infinity, hi = -Infinity, la = Infinity, lb = -Infinity;
    const walk = (c) => {
      if (typeof c[0] === "number") {
        lo = Math.min(lo, c[0]); hi = Math.max(hi, c[0]);
        la = Math.min(la, c[1]); lb = Math.max(lb, c[1]);
      } else c.forEach(walk);
    };
    regions.features.forEach((f) => walk(f.geometry.coordinates));
    const midLat = (la + lb) / 2;
    const kx = Math.cos((midLat * Math.PI) / 180);
    const pad = 24;
    const sx = (W - 2 * pad) / ((hi - lo) * kx);
    const sy = (H - 2 * pad) / (lb - la);
    const s = Math.min(sx, sy);
    const ox = pad + (W - 2 * pad - (hi - lo) * kx * s) / 2;
    const oy = pad + (H - 2 * pad - (lb - la) * s) / 2;
    const P = (lon, lat) => [ox + (lon - lo) * kx * s, oy + (lb - lat) * s];

    const featurePath = (coords) => {
      const rings = Array.isArray(coords[0][0]) ? coords : [coords];
      return rings
        .map(
          (ring) =>
            "M" +
            ring.map((p) => P(p[0], p[1]).map((v) => v.toFixed(1)).join(",")) +
            "Z",
        )
        .join(" ");
    };
    const paths = regions.features.map((f) => ({
      name: f.properties.name,
      d: featurePath(f.geometry.coordinates),
    }));
    return { path: paths, xy: Object.fromEntries(cities.map((c) => [c.slug, P(c.lon, c.lat)])) };
  }, [cities]);

  return (
    <div className="map-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="map" role="img" aria-label="Carte de France, 20 villes universitaires">
        {path.map((p) => (
          <path key={p.name} d={p.d} className="region" aria-label={p.name} />
        ))}
        {cities.map((c) => {
          const [x, y] = xy[c.slug];
          const top = c.rang <= 5;
          return (
            <g
              key={c.slug}
              className="city-dot"
              tabIndex={0}
              role="button"
              aria-label={`${c.nom} — score ${c.score_global}/100, rang ${c.rang}`}
              onClick={() => navigate(`/ville/${c.slug}`)}
              onKeyDown={(e) => e.key === "Enter" && navigate(`/ville/${c.slug}`)}
              onMouseEnter={() => setHover(c)}
              onMouseLeave={() => setHover(null)}
            >
              {top && <circle cx={x} cy={y} r="14" fill="none" stroke={scoreColor(c.score_global)} strokeWidth="2" className="pulse" />}
              <circle cx={x} cy={y} r={c.rang <= 5 ? 8 : 6} fill={scoreColor(c.score_global)} stroke="#fff" strokeWidth="1.6" />
              {c.rang <= 5 && (
                <text x={x + 12} y={y + 4} className="city-label">
                  {c.nom}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {hover && (
        <div className="map-tip">
          <b>{hover.nom}</b> · {hover.score_global}/100 · {hover.rang}
          <sup>e</sup>/{cities.length}
        </div>
      )}
      <p className="map-note">Contours régionaux simplifiés (découpage antérieur à 2016) — crédits geoBoundaries / IGN.</p>
    </div>
  );
}
