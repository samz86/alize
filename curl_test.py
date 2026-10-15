# -*- coding: utf-8 -*-
"""
curl_test.py — Test final : scope technique seul vs scope applicatif+technique.
Si aucun des deux n'ouvre l'API -> propagation de l'abonnement côté France Travail.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")
cid = os.getenv("FT_CLIENT_ID", "")
sec = os.getenv("FT_CLIENT_SECRET", "")

AUTH = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
URL = "https://api.francetravail.io/partenaire/stats-offres-demandes-emploi/v1/demandeurs"

essais = [
    "api_stats-offres-demandes-emploiv1",                      # seul
    f"application_{cid} api_stats-offres-demandes-emploiv1",    # les deux (contrôle)
]

for scope in essais:
    r = requests.post(
        AUTH,
        data={"grant_type": "client_credentials", "scope": scope},
        auth=(cid, sec),
        timeout=30,
    )
    if r.status_code != 200:
        print(f"token refusé : {r.text[:150]}")
        continue
    tok = r.json()["access_token"]
    r2 = requests.get(URL, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    verdict = "  <<< *** API ACCESSIBLE ***" if r2.status_code != 403 else ""
    print(f"token OK ({scope[:50]}...) -> API HTTP {r2.status_code}{verdict}")
    if r2.status_code != 403:
        print("Body:", r2.text[:400])

print("\n>>> Colle toute cette sortie dans le chat.")