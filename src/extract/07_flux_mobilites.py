# -*- coding: utf-8 -*-
"""
07_flux_mobilites.py — Flux de mobilités scolaires domicile -> lieu d'études (INSEE, RP 2023)

Source : INSEE, « Mobilités scolaires en 2023 : déplacements domicile - lieu d'études »
         (base flux de mobilité, CSV ~4 Mo, ensemble des flux, géographie au 01/01/2026)
         https://www.insee.fr/fr/statistiques/8998322
         ⚠️ Téléchargement manuel (le portail INSEE bloque l'accès automatisé).
         ⚠️ Prendre le CSV (ensemble des flux), PAS le XLSX (flux > 100 seulement).
         ⚠️ Paris / Lyon / Marseille diffusés au niveau ARRONDISSEMENT MUNICIPAL (ARM)
            uniquement -> le script somme les ARM pour reconstituer la commune
            (75101-75120 -> 75056, 69381-69389 -> 69123, 13201-13216 -> 13055).

Sortie : data/raw/mobilites_scolaires_villes.csv (1 ligne par ville, jointure code_insee)
Colonnes sortie :
  - code_insee, ville
  - flux_entree_educatif   : population scolarisée étudiant DANS la ville (bassin d'accueil)
  - flux_sortie_residents  : résidents scolarisés de la ville étudiant ailleurs
  - locaux                 : résidents étudiant dans leur commune
  - part_locaux           : locaux / (locaux + flux_sortie_residents), en %
  - ratio_attractivite     : flux_entree / flux_sortie (>1 = la ville attire plus
                             d'étudiants extérieurs qu'elle n'en « exporte »)
  - top5_provenances       : codes+libellés des 5 communes d'origine principales
  - top5_destinations      : codes+libellés des 5 lieux d'études principaux des résidents
  - millesime              : 2023

Usage :
  python src/extract/07_flux_mobilites.py --inspect     # AVANT TOUT : structure du fichier
  python src/extract/07_flux_mobilites.py               # run complet -> CSV sortie
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Référentiel des 20 villes (codes INSEE officiels, cf. 06_api_geo.py)
# ---------------------------------------------------------------------------
VILLES = {
    "75056": "Paris", "69123": "Lyon", "31555": "Toulouse", "59350": "Lille",
    "33063": "Bordeaux", "44109": "Nantes", "34172": "Montpellier", "35238": "Rennes",
    "67482": "Strasbourg", "38185": "Grenoble", "13055": "Aix-en-Provence",
    "54395": "Nancy", "86194": "Poitiers", "37261": "Tours", "63113": "Clermont-Ferrand",
    "14118": "Caen", "06088": "Nice", "51454": "Reims", "49007": "Angers", "21231": "Dijon",
}

# Regroupement ARM -> commune mère (Paris, Lyon, Marseille)
ARM_PREFIXES = {"751": "75056", "693": "69123", "132": "13055"}

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
OUT_PATH = RAW_DIR / "mobilites_scolaires_villes.csv"


def norm_commune(code: str) -> str:
    """Recode un code géographique (résidence OU lieu d'études) :
    ARM de Paris/Lyon/Marseille -> code de la commune mère, sinon inchangé."""
    code = str(code).strip()
    if len(code) == 5 and code[:3] in ARM_PREFIXES:
        return ARM_PREFIXES[code[:3]]
    return code


def find_source_file() -> Path:
    """Cherche le CSV mobilités scolaires téléchargé manuellement dans data/raw/."""
    patterns = ["*mobilite*scolaire*", "*scolaire*2023*", "*flux*scolaire*", "*SCOL*"]
    for pat in patterns:
        hits = sorted(RAW_DIR.glob(pat + ".csv"))
        if hits:
            return hits[0]
    raise SystemExit(
        f"[ERREUR] CSV source introuvable dans {RAW_DIR}\n"
        "Télécharge-le depuis https://www.insee.fr/fr/statistiques/8998322\n"
        "(bouton 'csv, 4 Mo' — ensemble des flux, PAS le xlsx)\n"
        "puis renomme-le par ex. mobilites_scolaires_2023.csv dans data/raw/."
    )


# ---------------------------------------------------------------------------
# Mode --inspect : structure réelle du fichier (noms de colonnes à confirmer)
# ---------------------------------------------------------------------------
def inspect(df: pd.DataFrame, path: Path):
    print("=" * 70)
    print(f"Fichier : {path}")
    print(f"Dimensions : {len(df):,} lignes × {df.shape[1]} colonnes")
    print("=" * 70)
    print("\nColonnes et types :")
    for c in df.columns:
        print(f"  {c!r:45s} {str(df[c].dtype):10s} ex: {df[c].iloc[0]!r}")

    print("\n5 premières lignes :")
    print(df.head(5).to_string())

    # Codes attendus : colonnes candidates résidence / lieu d'études / flux
    col_res = next((c for c in df.columns if c.upper() in ("COMMUNE", "D_RES", "CODGEO")), None)
    col_etu = next((c for c in df.columns if c.upper() in ("DCETU", "D_ETU")), None)
    col_flux = next((c for c in df.columns if "NBFLUX" in c.upper()), None)

    print("\nDétection des colonnes :")
    print(f"  résidence  = {col_res!r}")
    print(f"  lieu étude = {col_etu!r}")
    print(f"  flux       = {col_flux!r}")

    if col_res and col_etu:
        res_codes = set(df[col_res].astype(str).str.strip())
        etu_codes = set(df[col_etu].astype(str).str.strip())
        print("\nVérification codes (présence côté résidence / côté lieu d'études) :")
        tests = [("75056", "Paris (commune)"), ("69123", "Lyon (commune)"),
                 ("75101", "Paris 1er ARM"), ("69381", "Lyon 1er ARM"),
                 ("31555", "Toulouse"), ("86194", "Poitiers")]
        for code, label in tests:
            print(f"  {label:20s} {code} : {'OUI' if code in res_codes else 'non'} / {'OUI' if code in etu_codes else 'non'}")

    print("\nStructure OK. Vérifie les points suivants avant le run complet :")
    print("  - résidence et lieu d'études détectés ;")
    print("  - villes ARM (Paris/Lyon) présentes sous forme d'arrondissements ;")
    print("  - valeurs de flux plausibles (estimations sondage RP, décimales normales).")


# ---------------------------------------------------------------------------
# Run complet
# ---------------------------------------------------------------------------
def run_full(df: pd.DataFrame, col_res: str, col_etu: str, col_flux: str):
    # Recodage ARM -> commune mère des DEUX côtés (résidence et lieu d'études)
    df = df.copy()
    df["_res"] = df[col_res].astype(str).str.strip().map(norm_commune)
    df["_etu"] = df[col_etu].astype(str).str.strip().map(norm_commune)
    df["_flux"] = pd.to_numeric(df[col_flux], errors="coerce").fillna(0)
    # NB : le champ est la population scolarisée de 2 ans ou plus -> inclut élèves
    # du primaire/collège/lycée. Limite méthodo à documenter : « bassin éducatif »
    # au sens large, pas uniquement le supérieur (le fichier détail RP avec l'âge
    # viendra affiner le taux de retenue des diplômés).

    # Libellés (confirmés par --inspect) : résidence = LIBGEO, lieu d'études = L_DCETU
    lib_res = "LIBGEO" if "LIBGEO" in df.columns else None
    lib_etu = "L_DCETU" if "L_DCETU" in df.columns else (
        next((c for c in df.columns if c.upper().startswith("L_") and c.upper().endswith(col_etu.upper())), None))

    def libelle(row, side):
        col = lib_res if side == "res" else lib_etu
        return str(row.get(col, "?")) if col else "?"

    def top5(sub, col, lib):
        g = sub.groupby(col)["_flux"].sum().sort_values(ascending=False)
        out = []
        for c, v in g.head(5).items():
            lab = "?"
            if lib and (sub[col] == c).any():
                lab = str(sub.loc[sub[col] == c, lib].iloc[0])
            out.append(f"{c} ({lab}): {int(v)}")
        return " | ".join(out)

    rows = []
    for code, ville in VILLES.items():
        # 1) Flux ENTRANTS : résidents d'ailleurs étudiant dans la ville
        entrants = df[(df["_etu"] == code) & (df["_res"] != code)]
        # 2) Flux LOCAUX : résidents étudiant dans leur commune
        locaux_df = df[(df["_etu"] == code) & (df["_res"] == code)]
        locaux = float(locaux_df["_flux"].sum())
        # 3) Flux SORTANTS : résidents de la ville étudiant ailleurs
        sortants = df[(df["_res"] == code) & (df["_etu"] != code)]
        flux_sortie = float(sortants["_flux"].sum())
        flux_entree = float(entrants["_flux"].sum())

        denom = locaux + flux_sortie
        part_locaux = 100 * locaux / denom if denom else float("nan")
        ratio = flux_entree / flux_sortie if flux_sortie else float("inf")

        rows.append({
            "code_insee": code, "ville": ville,
            "flux_entree_educatif": int(flux_entree),
            "flux_sortie_residents": int(flux_sortie),
            "locaux": int(locaux),
            "part_locaux": round(part_locaux, 1),
            "ratio_attractivite": round(ratio, 2),
            "top5_provenances": top5(entrants, "_res", lib_res),
            "top5_destinations": top5(sortants, "_etu", lib_etu),
            "millesime": 2023,
        })

    out = pd.DataFrame(rows).sort_values("ville")
    out.to_csv(OUT_PATH, index=False)
    print(f"[OK] {OUT_PATH} écrit — {len(out)} villes\n")
    print(out[["ville", "flux_entree_educatif", "flux_sortie_residents", "locaux",
               "part_locaux", "ratio_attractivite"]].to_string(index=False))
    print("\nContrôles de plausibilité :")
    print("  - Paris/Lyon : flux entrants très élevés (ARM sommés) ;")
    print("  - villes universitaires : ratio_attractivite > 1 ;")
    print("  - flux < 200 : ordres de grandeur (sondage RP), à interpréter avec prudence.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true", help="affiche la structure du fichier et s'arrête")
    args = ap.parse_args()

    path = find_source_file()
    # Les CSV INSEE base flux sont généralement en ';' — sniffer pour être robuste.
    df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")

    if args.inspect:
        inspect(df, path)
        return

    # Résolution des colonnes (mêmes heuristiques que --inspect, échec explicite sinon)
    col_res = next((c for c in df.columns if c.upper() in ("COMMUNE", "D_RES", "CODGEO")), None)
    col_etu = next((c for c in df.columns if c.upper() in ("DCETU", "D_ETU")), None)
    col_flux = next((c for c in df.columns if "NBFLUX" in c.upper()), None)
    if not (col_res and col_etu and col_flux):
        sys.exit(f"[ERREUR] Colonnes non résolues (res={col_res}, etu={col_etu}, flux={col_flux}). "
                 "Lance d'abord --inspect pour vérifier la structure du fichier.")
    print(f"[INFO] colonnes : résidence={col_res!r}, lieu d'études={col_etu!r}, flux={col_flux!r}")
    run_full(df, col_res, col_etu, col_flux)


if __name__ == "__main__":
    main()