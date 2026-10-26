#!/usr/bin/env python
"""
build_site_data.py — Alizé site : génération des données publiques.
======================================================================

Génère public/data/cities.json, formations.json (et meta.json) depuis les
sorties de l'ETL :

  - data/processed/villes_scoring.csv          (scores + indicateurs, obligatoire)
  - data/processed/parcoursup_villes.csv      (offre de formations Parcoursup)
  - data/processed/parcoursup_familles.csv    (détail ville x famille)
  - data/raw/ancrage_diplomes_villes.csv       (taux d'ancrage, arrivées — KPI signature)
  - data/raw/mobilites_scolaires_villes.csv    (ratio d'attractivité scolaire)
  - data/raw/detail_mobilites_villes.csv      (part des 18-24 accueillis)
  - site/content/villes/*.md                   (intro éditoriale + note de risque)

Les CSV optionnels : les champs absents restent à null et le site affiche
« à venir » (aucun chiffre inventé, traçabilité conservée).

Parcoursup : multi-étiquettes — une formation peut compter dans plusieurs
familles (« Etudes de santé,Licence »). Le total par famille peut donc
dépasser le nombre de formations de la ville. Session la plus récente
(2026 au moment de l'écriture), voir src/extract/10_parcoursup.py.

Usage (depuis la racine du dépôt) :
    python site/transform/build_site_data.py

Contrôles de plausibilité en fin de script : nombre de villes, valeurs
manquantes, cohérence des rangs.
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[2] if Path(__file__).resolve().parent.name == "transform" else Path(__file__).resolve().parents[1]
SITE = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "transform" else Path(__file__).resolve().parent
PROCESSED = RACINE / "data" / "processed"
RAW = RACINE / "data" / "raw"
CONTENU = SITE / "content" / "villes"
OUT = SITE / "public" / "data"

# Coordonnées des chefs-lieux (API Géo / INSEE) — référentiel stable.
LATLON = {
    "Paris": (48.8566, 2.3522), "Lyon": (45.7640, 4.8357), "Toulouse": (43.6045, 1.4442),
    "Lille": (50.6292, 3.0573), "Bordeaux": (44.8378, -0.5792), "Nantes": (47.2184, -1.5536),
    "Montpellier": (43.6109, 3.8763), "Rennes": (48.1173, -1.6778), "Strasbourg": (48.5734, 7.7521),
    "Grenoble": (45.1885, 5.7245), "Aix-en-Provence": (43.5297, 5.4474), "Nancy": (48.6921, 6.1844),
    "Poitiers": (46.5802, 0.3404), "Tours": (47.3941, 0.6848), "Clermont-Ferrand": (45.7772, 3.0870),
    "Caen": (49.1829, -0.3707), "Nice": (43.7102, 7.2620), "Reims": (49.2583, 4.0317),
    "Angers": (47.4784, -0.5632), "Dijon": (47.3220, 5.0415),
}


def slugify(nom: str) -> str:
    s = nom.lower()
    s = re.sub(r"[éèêë]", "e", s)
    s = re.sub(r"[àâä]", "a", s)
    s = re.sub(r"[îï]", "i", s)
    s = re.sub(r"[ôö]", "o", s)
    s = re.sub(r"[ùûü]", "u", s)
    s = re.sub(r"[ç]", "c", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def lire_annotes(contenu_ville: Path):
    """Extrait l'intro éditoriale et la note de risque d'une fiche markdown."""
    if not contenu_ville.exists():
        return "", None
    md = contenu_ville.read_text(encoding="utf-8")
    m = re.search(r"Note\s*:\s*([ABC])", md)
    risque = m.group(1) if m else None
    paras = [p.strip() for p in re.split(r"\n\n+", md) if p.strip() and not p.startswith("#") and not p.startswith("|")]
    return (paras[0] if paras else ""), risque


def main():
    scoring_path = PROCESSED / "villes_scoring.csv"
    if not scoring_path.exists():
        print(f"[ERREUR] {scoring_path} introuvable. Lancer d'abord transform/scores.py.")
        sys.exit(1)
    df = pd.read_csv(scoring_path)
    df.columns = [c.strip() for c in df.columns]
    ville_col = next(c for c in df.columns if c.lower() in ("ville", "nom_ville"))
    df[ville_col] = df[ville_col].str.strip()

    # --- mobilité (optionnel) ---
    ancrage, mobilites, detail = {}, {}, {}
    p = RAW / "ancrage_diplomes_villes.csv"
    if p.exists():
        a = pd.read_csv(p)
        vcol = next(c for c in a.columns if "ville" in c.lower())
        acol = next((c for c in a.columns if "ancrage" in c.lower()), None)
        rcol = next((c for c in a.columns if "arrivee" in c.lower() and "1an" in c.lower()), None)
        scol = next((c for c in a.columns if c.lower().startswith("dipl")), None)
        for _, r in a.iterrows():
            v = str(r[vcol]).strip()
            stock = float(r[scol]) if scol and pd.notna(r[scol]) else None
            ancrage[v] = {
                "taux_ancrage": round(float(r[acol]), 1) if acol and pd.notna(r[acol]) else None,
                "arrivees_relatives": round(100 * float(r[rcol]) / stock, 1) if (rcol and scol and stock and pd.notna(r[rcol])) else None,
            }
    p = RAW / "mobilites_scolaires_villes.csv"
    if p.exists():
        m = pd.read_csv(p)
        vcol = next(c for c in m.columns if "ville" in c.lower())
        rcol = next((c for c in m.columns if "ratio" in c.lower()), None)
        for _, r in m.iterrows():
            v = str(r[vcol]).strip()
            if rcol and pd.notna(r[rcol]):
                mobilites[v] = round(float(r[rcol]), 2)
    p = RAW / "detail_mobilites_villes.csv"
    if p.exists():
        d = pd.read_csv(p)
        vcol = next(c for c in d.columns if "ville" in c.lower())
        pcol = next((c for c in d.columns if "18_24" in c and "part" in c.lower()), None)
        for _, r in d.iterrows():
            v = str(r[vcol]).strip()
            if pcol and pd.notna(r[pcol]):
                detail[v] = round(float(r[pcol]), 1)

    # --- formations Parcoursup (optionnel, data/processed) ---
    parcoursup = {}
    p = PROCESSED / "parcoursup_villes.csv"
    if p.exists():
        f = pd.read_csv(p)
        f.columns = [c.strip() for c in f.columns]
        for _, r in f.iterrows():
            v = str(r["ville"]).strip()
            parcoursup[v] = {
                "nb_formations": int(r["nb_formations"]),
                "nb_etablissements": int(r["nb_etablissements"]),
                "familles_presentes": int(r["familles_presentes"]),
                "part_apprentissage": round(float(r["part_apprentissage"]), 1) if pd.notna(r["part_apprentissage"]) else None,
            }
    p = PROCESSED / "parcoursup_familles.csv"
    if p.exists():
        pf = pd.read_csv(p)
        pf.columns = [c.strip() for c in pf.columns]
        for v, g in pf.groupby("ville"):
            g = g.sort_values("nb_formations", ascending=False)
            parcoursup.setdefault(str(v).strip(), {})["familles"] = [
                {"famille": str(r["famille"]).strip(), "nb": int(r["nb_formations"])}
                for _, r in g.iterrows()
            ]

    def num(x, arr=1):
        if x is None or pd.isna(x):
            return None
        return round(float(x), arr)

    def col(*cands):
        for c in cands:
            if c in df.columns:
                return c
        return None

    villes = []
    for _, r in df.iterrows():
        nom = str(r[ville_col]).strip()
        slug = slugify(nom)
        intro, risque = lire_annotes(CONTENU / f"{slug}.md")
        anc = ancrage.get(nom, {})
        villes.append({
            "slug": slug, "nom": nom,
            "code_insee": str(r.get("code_insee", "")),
            "lat": LATLON.get(nom, (None, None))[0], "lon": LATLON.get(nom, (None, None))[1],
            "rang": int(r["rang"]), "score_global": num(r["score_global"]),
            "score_logement": num(r["score_logement"]), "score_emploi": num(r["score_emploi"]),
            "score_demographie": num(r["score_demographie"]), "score_formation": num(r["score_formation"]),
            "effectifs": num(r[col("effectifs", "effectif_etudiants", "etudiants")], 0),
            "population": num(r[col("pop", "population", "pop_totale")], 0),
            "densite_etudiante": num(r[col("densite_etudiante")]),
            "part_15_24": num(r[col("part_15_24")]), "part_diplomes_sup": num(r[col("part_dipl_sup", "part_diplomes_sup")]),
            "part_cadres": num(r[col("part_cadres")]), "part_prof_interm": num(r[col("part_prof_interm")]),
            "taux_chomage": num(r[col("taux_chomage")]), "ecart_chomage": num(r[col("ecart_chomage")], 2),
            "prix_m2": num(r[col("prix_m2")]),
            "prix_impute": slug == "strasbourg",
            "taux_effort": num(r[col("taux_effort_logement", "taux_effort")]),
            "prix_m2_diplome": num(r[col("prix_m2_diplome")]),
            "risque": risque, "intro": intro,
            "taux_ancrage": anc.get("taux_ancrage"), "arrivees_relatives": anc.get("arrivees_relatives"),
            "dynamique": None,
            "ratio_attractivite": mobilites.get(nom), "part_18_24_accueillis": detail.get(nom),
        })

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cities.json").write_text(json.dumps(villes, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- formations Parcoursup -> public/data/formations.json (clé = slug) ---
    formations = {}
    for v in villes:
        f = parcoursup.get(v["nom"])
        if f:
            formations[v["slug"]] = f
    (OUT / "formations.json").write_text(json.dumps(formations, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- contrôles de plausibilité ---
    print(f"cities.json : {len(villes)} villes.")
    n_ancrage = sum(1 for v in villes if v["taux_ancrage"] is not None)
    n_ratio = sum(1 for v in villes if v["ratio_attractivite"] is not None)
    n_risque = sum(1 for v in villes if v["risque"])
    print(f"  taux d'ancrage présents : {n_ancrage}/20 ; ratios scolaires : {n_ratio}/20 ; notes de risque : {n_risque}/20.")
    print(f"formations.json : {len(formations)} villes (source Parcoursup, data/processed, multi-étiquettes documentées).")
    if formations:
        nf = {v["nom"]: f["nb_formations"] for v in villes for s, f in formations.items() if s == v["slug"]}
        noms_tries = sorted(nf, key=nf.get, reverse=True)[:3]
        print(f"  top 3 volumes : " + " ; ".join(f"{n} ({nf[n]:,})".replace(",", " ") for n in noms_tries) + ".")
    manq = [v["nom"] for v in villes if v["score_global"] is None]
    if manq:
        print(f"  [ATTENTION] score global manquant : {manq}")
    scores = sorted((v["score_global"] or 0) for v in villes)
    print(f"  scores globaux : min {scores[0]} / max {scores[-1]} (attendu ≈ 32,9 à 66,5).")
    print("Limites méthodo inchangées : voir public/data/meta.json et la page La démarche du site.")


if __name__ == "__main__":
    main()