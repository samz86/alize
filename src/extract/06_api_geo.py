"""
Extraction du référentiel des communes via l'API Geo (api.gouv.fr).
V2 : ajoute latitude/longitude (champ 'centre') — sert au quiz (distance
domicile -> villes du panel) et à la future carte du site React.
Relançable sans risque : réécrit le référentiel complet à chaque fois.
"""
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
    """Recherche la commune par nom, puis récupère la fiche détaillée par code
    (le champ 'centre' — lat/lon — n'est retourné QUE sur /communes/{code})."""
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
    if not resultats:
        return None
    commune = resultats[0]

    # 2e appel : fiche détaillée — 'centre' est une géométrie, il FAUT le
    # demander explicitement via fields, sinon l'API ne le renvoie pas.
    fiche = requests.get(
        f"https://geo.api.gouv.fr/communes/{commune['code']}",
        params={"fields": "centre"},
    )
    fiche.raise_for_status()
    commune.update(fiche.json())
    return commune

def main():
    lignes = []
    for ville in VILLES:
        print(f"Récupération : {ville}...")
        commune = get_commune(ville)
        if commune:
            centre = commune.get("centre") or {}
            # ⚠️ Format GeoJSON : {"type": "Point", "coordinates": [lon, lat]}
            # L'ordre est [longitude, latitude] — convention piège de GeoJSON.
            coords = centre.get("coordinates") or []
            lat = round(float(coords[1]), 5) if len(coords) >= 2 else None
            lon = round(float(coords[0]), 5) if len(coords) >= 2 else None
            lignes.append({
                "ville": ville,
                "code_insee": commune["code"],
                "population": commune.get("population"),
                "region": commune["region"]["nom"],
                "latitude": lat,
                "longitude": lon,
            })
            if lat is None:
                print(f"  ⚠️ {ville} : pas de coordonnées retournées")
        else:
            print(f"  ⚠️ Aucun résultat pour {ville}")
        time.sleep(0.2)

    df = pd.DataFrame(lignes)
    df.to_csv("data/raw/referentiel_villes.csv", index=False)
    print(f"\n✅ {len(df)} villes sauvegardées dans data/raw/referentiel_villes.csv")
    print(df)

if __name__ == "__main__":
    main()