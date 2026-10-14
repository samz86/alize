"""Extraction du référentiel des communes via l'API Geo (api.gouv.fr)."""
import time
import requests
import pandas as pd

VILLES = [
    "Paris", "Lyon", "Toulouse", "Lille", "Bordeaux",
    "Nantes", "Montpellier", "Rennes", "Strasbourg", "Grenoble",
    "Aix-en-Provence", "Nancy", "Poitiers", "Tours", "Clermont-Ferrand",
    "Caen", "Nice", "Reims", "Angers", "Dijon"
]

def get_commune(nom):
    """Interroge l'API Geo et retourne le premier résultat (code + population)."""
    url = "https://geo.api.gouv.fr/communes"
    params = {
        "nom": nom,
        "fields": "code,population,region",
        "format": "json",
        "boost": "population",
        "limit": 5
    }
    reponse = requests.get(url, params=params)
    reponse.raise_for_status()
    resultats = reponse.json()
    return resultats[0] if resultats else None

def main():
    lignes = []
    for ville in VILLES:
        print(f"Récupération : {ville}...")
        commune = get_commune(ville)
        if commune:
            lignes.append({
                "ville": ville,
                "code_insee": commune["code"],
                "population": commune.get("population"),
                "region": commune["region"]["nom"],
            })
        else:
            print(f"  ⚠️ Aucun résultat pour {ville}")
        time.sleep(0.2)

    df = pd.DataFrame(lignes)
    df.to_csv("data/raw/referentiel_villes.csv", index=False)
    print(f"\n✅ {len(df)} villes sauvegardées dans data/raw/referentiel_villes.csv")
    print(df)

if __name__ == "__main__":
    main()
