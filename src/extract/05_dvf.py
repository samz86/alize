"""
05_dvf.py — Prix immobilier au m² (DVF brut DGFiP, data.gouv.fr)

Source : fichier annuel "Valeurs foncières" (DVF brut, tout-départements,
téléchargement direct sans compte). Mise à jour data.gouv du 12/10/2026.
NB : la livraison 2026 sépare 'Code departement' et 'Code commune' (3 chiffres) —
on reconstruit le code INSEE complet : dep + commune.zfill(3).

Sortie : data/raw/dvf_prix_m2.csv
  colonnes du référentiel + prix_m2_median_appart, n_transactions, annee

⚠️ Strasbourg : aucune donnée DVF (Alsace-Moselle) → prix_m2 vide.
Lancement : python src/extract/05_dvf.py  (venv activé, PAS py -3.12)
"""

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw"
ZIP_PATH = RAW_DIR / "valeursfoncieres-2025.txt.zip"
OUT_PATH = RAW_DIR / "dvf_prix_m2.csv"

DVF_URL = (
    "https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres/"
    "20261012-171642/valeursfoncieres-2025.txt.zip"
)
ANNEE = 2025

# Ville -> codes INSEE complets (dep + commune)
VILLES_CODES = {
    "Paris": [f"751{i:02d}" for i in range(1, 21)],
    "Lyon": [f"6938{i}" for i in range(1, 10)],
    "Toulouse": ["31555"],
    "Lille": ["59350"],
    "Bordeaux": ["33063"],
    "Nantes": ["44109"],
    "Montpellier": ["34172"],
    "Rennes": ["35238"],
    "Strasbourg": ["67482"],   # aucune donnée attendue (Alsace-Moselle)
    "Grenoble": ["38185"],
    "Aix-en-Provence": ["13001"],
    "Nancy": ["54395"],
    "Poitiers": ["86194"],
    "Tours": ["37261"],
    "Clermont-Ferrand": ["63113"],
    "Caen": ["14118"],
    "Nice": ["06088"],
    "Reims": ["51454"],
    "Angers": ["49007"],
    "Dijon": ["21231"],
}


def download_dvf() -> None:
    """Télécharge le zip annuel (~71 Mo) s'il n'est pas déjà présent."""
    if ZIP_PATH.exists():
        print(f"[OK] {ZIP_PATH.name} déjà présent, téléchargement sauté.")
        return
    print(f"[...] Téléchargement {DVF_URL}")
    with requests.get(DVF_URL, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(ZIP_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    print(f"[OK] Téléchargé : {ZIP_PATH.name} ({ZIP_PATH.stat().st_size / 1e6:.0f} Mo)")


def read_txt_from_zip() -> pd.DataFrame:
    """Lit le .txt contenu dans le zip et reconstruit le code INSEE complet."""
    with zipfile.ZipFile(ZIP_PATH) as zf:
        txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        with zf.open(txt_name) as fh:
            df = pd.read_csv(
                io.TextIOWrapper(fh, encoding="utf-8", errors="replace"),
                sep="|",
                decimal=",",  # nombres à la française (468000,00)
                usecols=[
                    "Valeur fonciere",
                    "Type local",
                    "Surface reelle bati",
                    "Code departement",
                    "Code commune",
                ],
                dtype={
                    "Valeur fonciere": "float64",
                    "Surface reelle bati": "float64",
                    "Type local": str,
                    "Code departement": str,
                    "Code commune": str,
                },
            )
    # Nettoyage des espaces parasites
    df["Type local"] = df["Type local"].str.strip()
    df["Code departement"] = df["Code departement"].str.strip()
    df["Code commune"] = df["Code commune"].str.strip()

    # Reconstruit le code INSEE 5 caractères : dep (2A/2B ou 01-95) + commune (3)
    df["code_insee"] = df["Code departement"].str.zfill(2) + df["Code commune"].str.zfill(3)

    print(f"[OK] DVF chargé : {len(df):,} lignes")
    print(f"[DEBUG] Exemple codes INSEE reconstruits : {df['code_insee'].dropna().unique()[:5].tolist()}")
    return df


def fetch_all_villes(df: pd.DataFrame) -> pd.DataFrame:
    """Médiane prix/m² des appartements par ville, trim 5-95 %."""
    df = df.copy()
    df["prix_m2"] = df["Valeur fonciere"] / df["Surface reelle bati"]

    appart = df[
        (df["Type local"] == "Appartement")
        & df["Valeur fonciere"].notna()
        & (df["Surface reelle bati"] > 9)  # écarte surfaces aberrantes
        & df["prix_m2"].notna()
        & (df["prix_m2"] > 100)            # écarte prix aberrants
        & (df["prix_m2"] < 30000)
    ]
    print(f"[DEBUG] Lignes appartements (France entière) : {len(appart):,}")

    rows = []
    for ville, codes in VILLES_CODES.items():
        sub = appart[appart["code_insee"].isin(codes)]
        n = len(sub)
        if n == 0:
            rows.append({"ville": ville, "prix_m2_median_appart": None, "n_transactions": 0, "annee": ANNEE})
            continue
        lo, hi = sub["prix_m2"].quantile([0.05, 0.95])
        trimmed = sub[(sub["prix_m2"] >= lo) & (sub["prix_m2"] <= hi)]
        rows.append(
            {
                "ville": ville,
                "prix_m2_median_appart": round(float(trimmed["prix_m2"].median()), 1),
                "n_transactions": int(n),
                "annee": ANNEE,
            }
        )
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    return out


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    download_dvf()
    df = read_txt_from_zip()
    out = fetch_all_villes(df)

    # Rattachement au référentiel des 20 villes (jointure sur le nom)
    ref_path = RAW_DIR / "referentiel_villes.csv"
    if ref_path.exists():
        ref = pd.read_csv(ref_path)
        nom_col = next((c for c in ["ville", "nom", "commune", "Ville"] if c in ref.columns), ref.columns[0])
        ref = ref.rename(columns={nom_col: "ville"})
        ref["ville_norm"] = ref["ville"].str.strip().str.lower()
        out["ville_norm"] = out["ville"].str.strip().str.lower()
        merged = (
            ref.merge(out, on="ville_norm", how="left", suffixes=("", "_dvf"))
            .drop(columns=["ville_norm", "ville_dvf"])
        )
        merged.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    else:
        out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"[OK] Écrit : {OUT_PATH}")


if __name__ == "__main__":
    main()