"""
01_mestr.py — Effectifs d'étudiants inscrits par commune (MESR / SIES).

Source : jeu « Effectifs d'étudiants inscrits (données agrégeables) »
https://data.enseignementsup-recherche.gouv.fr/explore/dataset/fr-esr-atlas_regional-effectifs-d-etudiants-inscrits_agregeables/

⚠️ Le portail MESR bloque le téléchargement automatisé : télécharger le CSV
manuellement depuis un navigateur (Export → CSV) et le placer dans
data/raw/mestr_brut.csv. Ce script lit ce fichier local.

Sortie : data/raw/mestr_effectifs.csv
  colonnes : ville, code_insee, rentree, effectif_etudiants
  (somme des effectifs par ville pour la dernière rentrée disponible)

Particularités du jeu MESR (validées le 15/10/2026) :
  - Paris publié par arrondissement (75101-75120) + une ligne résiduelle 75056
  - Lyon publié par arrondissement (69381-69389) + une ligne résiduelle 69123
  - Codes différents des codes INSEE officiels : Strasbourg 67482 (≠67488),
    Reims 51454 (≠45487), Dijon 21231 (≠21319)
  - Limites documentées : Paris = commune seule (~415k, hors petite couronne) ;
    Grenoble sous-estimé (campus à Saint-Martin-d'Hères)

Modes :
  python src/extract/01_mestr.py            # run normal
  python src/extract/01_mestr.py --inspect   # affiche les colonnes + 5 lignes, ne produit rien
"""

import argparse
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Référentiel des 20 villes : codes MESR (cf. particularités ci-dessus)
# ---------------------------------------------------------------------------
VILLES = {
    "Paris": "75056",
    "Lyon": "69123",
    "Toulouse": "31555",
    "Lille": "59350",
    "Bordeaux": "33063",
    "Nantes": "44109",
    "Montpellier": "34172",
    "Rennes": "35238",
    "Strasbourg": "67482",   # code MESR, pas 67488
    "Grenoble": "38185",
    "Aix-en-Provence": "13001",
    "Nancy": "54395",
    "Poitiers": "86194",
    "Tours": "37261",
    "Clermont-Ferrand": "63113",
    "Caen": "14118",
    "Nice": "06088",
    "Reims": "51454",       # code MESR, pas 45487
    "Angers": "49007",
    "Dijon": "21231",       # code MESR, pas 21319
}

RAW_PATH = Path("data/raw/mestr_brut.csv")
OUT_PATH = Path("data/raw/mestr_effectifs.csv")


def normalise_code(s: pd.Series) -> pd.Series:
    """Codes communes en chaînes 'DDDDD' (zéros de tête conservés)."""
    return (s.astype(str).str.strip()
             .str.replace(r"\.0$", "", regex=True)
             .str.zfill(5))


def ville_depuis_code(code: str) -> str | None:
    """Retourne le nom de ville pour un code donné, en agrégeant les arrondissements."""
    if code.startswith("751"):        # Paris 1er-20e → 75101-75120
        return "Paris"
    if code.startswith("6938"):       # Lyon 1er-9e → 69381-69389
        return "Lyon"
    return {v: k for k, v in VILLES.items()}.get(code)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true",
                        help="Affiche les colonnes et 5 lignes du CSV brut, puis s'arrête.")
    args = parser.parse_args()

    if not RAW_PATH.exists():
        raise SystemExit(
            f"❌ Fichier introuvable : {RAW_PATH}\n"
            "Télécharge le CSV depuis :\n"
            "https://data.enseignementsup-recherche.gouv.fr/explore/dataset/"
            "fr-esr-atlas_regional-effectifs-d-etudiants-inscrits_agregeables/export/\n"
            "(Export → CSV) et place-le dans data/raw/mestr_brut.csv"
        )

    # ------------------------------------------------------------------ inspect
    if args.inspect:
        df = pd.read_csv(RAW_PATH, sep=None, engine="python", nrows=5)
        full = pd.read_csv(RAW_PATH, sep=None, engine="python", usecols=[0])
        print("=== INSPECTION ===")
        print(f"Colonnes ({len(df.columns)}) : {list(df.columns)}")
        print(f"Lignes totales (approx.) : {len(full)}")
        print("\n5 premières lignes :")
        print(df.to_string())
        print("\n→ Colle cette sortie à Vibe pour valider le mapping avant le run complet.")
        return

    # ------------------------------------------------------------------ run
    df = pd.read_csv(RAW_PATH, sep=None, engine="python")
    print(f"CSV brut : {len(df)} lignes")

    # Nettoyage du BOM + apostrophes typographiques
    df.columns = [c.lstrip("\ufeff").strip() for c in df.columns]
    col_code = "Code commune"
    col_rentree = "Année universitaire"
    col_eff = next(c for c in df.columns
                   if c.replace("\u2019", "'") == "Nombre total d'étudiants inscrits")

    # Codes normalisés + mapping vers les 20 villes (arrondissements inclus)
    df = df.copy()
    df["code_insee"] = normalise_code(df[col_code])
    df["ville"] = df["code_insee"].map(ville_depuis_code)
    df = df.dropna(subset=["ville"])   # garde uniquement les 20 villes

    # Effectifs en numérique
    df["effectif"] = pd.to_numeric(df[col_eff], errors="coerce")
    df = df.dropna(subset=["effectif"])

    # Dernière rentrée disponible (ex. '2025-26')
    df["rentree"] = df[col_rentree].astype(str).str.strip()
    derniere = df["rentree"].max()
    print(f"Dernière rentrée disponible : {derniere}")
    df = df[df["rentree"] == derniere]

    # Somme par ville (multi-lignes par commune : sexe, regroupement, secteur…)
    out = (df.groupby(["ville", "rentree"], as_index=False)
             .agg(effectif_etudiants=("effectif", "sum"))
             .sort_values("effectif_etudiants", ascending=False))
    # Code INSEE officiel de la ville (pour jointure avec le référentiel)
    codes_officiels = {
        "Paris": "75056", "Lyon": "69123", "Toulouse": "31555", "Lille": "59350",
        "Bordeaux": "33063", "Nantes": "44109", "Montpellier": "34172",
        "Rennes": "35238", "Strasbourg": "67488", "Grenoble": "38185",
        "Aix-en-Provence": "13001", "Nancy": "54395", "Poitiers": "86194",
        "Tours": "37261", "Clermont-Ferrand": "63113", "Caen": "14118",
        "Nice": "06088", "Reims": "45487", "Angers": "49007", "Dijon": "21319",
    }
    out["code_insee"] = out["ville"].map(codes_officiels)
    out = out[["ville", "code_insee", "rentree", "effectif_etudiants"]]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"\n✅ Écrit : {OUT_PATH} ({len(out)} villes)")
    print("\nContrôle rapide (attendu ~ Paris 600k, Lyon 170k, Toulouse 110k) :")
    print(out.to_string(index=False))

    villes_manquantes = set(VILLES) - set(out["ville"])
    if villes_manquantes:
        print(f"\n⚠️ Villes sans donnée : {sorted(villes_manquantes)}")


if __name__ == "__main__":
    main()