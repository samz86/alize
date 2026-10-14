"""Extraction DVF — prix médian au m² (appartements) par ville.

Source : DGFiP / data.economie.gouv.fr (dataset DVF, API explore v2.1).
Sortie : data/raw/dvf_prix.csv
NB : Strasbourg (67) non couvert par le DVF -> prix_m2 vide.
"""

import time
import pandas as pd
import requests

API = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/dvf/records"
)
DATE_MIN = "2025-10-01"   # 12 derniers mois de mutations
PAGE = 100


def fetch_ville(code_insee: str) -> pd.DataFrame:
    """Récupère toutes les transactions d'appartements d'une commune."""
    rows, offset = [], 0
    while True:
        params = {
            "where": (
                f'code_commune="{code_insee}" AND type_local="Appartement" '
                f'AND date_mutation>="{DATE_MIN}"'
            ),
            "limit": PAGE,
            "offset": offset,
        }
        r = requests.get(API, params=params, timeout=60)
        r.raise_for_status()
        batch = r.json().get("results", [])
        rows.extend(batch)
        if len(batch) < PAGE:
            return pd.DataFrame(rows)
        offset += PAGE
        time.sleep(0.5)  # on reste sympa avec l'API


def prix_m2_median(df: pd.DataFrame) -> float | None:
    if df.empty:
        return None
    d = df.dropna(subset=["valeur_fonciere", "surface_reelle_bati"])
    d = d[d["surface_reelle_bati"] > 5]
    d = d.assign(prix_m2=d["valeur_fonciere"] / d["surface_reelle_bati"])
    # coupe les 5% extrêmes de chaque côté
    lo, hi = d["prix_m2"].quantile([0.05, 0.95])
    d = d[(d["prix_m2"] >= lo) & (d["prix_m2"] <= hi)]
    return round(d["prix_m2"].median(), 1) if not d.empty else None


def main():
    ref = pd.read_csv("data/raw/referentiel_villes.csv", dtype={"code_insee": str})
    out = []
    for _, row in ref.iterrows():
        print(f"→ {row['ville']} ({row['code_insee']})...", flush=True)
        try:
            df = fetch_ville(row["code_insee"])
            p = prix_m2_median(df)
        except Exception as e:
            print(f"  ⚠️ erreur : {e}")
            p = None
        out.append({
            "code_insee": row["code_insee"],
            "ville": row["ville"],
            "prix_m2_appart": p,
            "nb_transactions": 0 if p is None else len(df),
        })
        print(f"  {p} €/m²", flush=True)
    res = pd.DataFrame(out)
    res.to_csv("data/raw/dvf_prix.csv", index=False)
    print(f"\n✅ {len(res)} villes -> data/raw/dvf_prix.csv")


if __name__ == "__main__":
    main()
