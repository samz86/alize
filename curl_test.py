"""
curl_test.py — Test minimaliste de l'API Marché du Travail France Travail.
Affiche le statut HTTP de chaque appel. Si tout renvoie 403 -> problème de scope
ou de propagation d'abonnement. Si 200 -> débloqué.

Correction support (INC2760848) : il faut DEUX scopes :
    application_{client_id} api_stats-offres-demandes-emploiv1 offresetdemandesemploi

Usage :
    python curl_test.py
"""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

RACINE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(RACINE, ".env"))

CLIENT_ID = os.getenv("FT_CLIENT_ID", os.getenv("FRANCE_TRAVAIL_CLIENT_ID", ""))
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET", os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", ""))

if not CLIENT_ID or not CLIENT_SECRET:
    sys.exit("[ERREUR] FT_CLIENT_ID / FT_CLIENT_SECRET absents du .env — "
             "vérifie les noms de variables (ce script accepte FT_* et FRANCE_TRAVAIL_*).")

TOKEN_URL = "https://api.francetravail.io/partenaire/oauth/v1/authorized_access_token"

BASE_URL = "https://api.francetravail.io/partenaire/stats-offres-demandes-emploi/v1"

RESSOURCES_A_TESTER = [
    "/referentiel/details-indicateurs",  # la plus légère, sans params
    "/demandeurs",
    "/offres",
    "/territoire",
    "/salaires",
]


def tester_ressource(token: str, ressource: str) -> None:
    """Appelle une ressource et affiche le statut + extrait du corps."""
    url = BASE_URL + ressource
    requete = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(requete, timeout=30) as reponse:
            corps = reponse.read().decode(errors="replace")
            print(f"  [{response_status(reponse)}] {ressource} -> {corps[:200]}")
    except HTTPError as e:
        corps = e.read().decode(errors="replace")
        print(f"  [HTTP {e.code}] {ressource} -> {corps[:200]}")
    except URLError as e:
        print(f"  [ERREUR RESEAU] {ressource} -> {e}")


def response_status(reponse) -> str:
    return f"HTTP {reponse.status}"


def tester_token(scope: str, etiquette: str) -> str | None:
    """Tente d'obtenir un token avec un scope donné. Retourne le token ou None."""
    donnees = json.dumps({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": scope,
    }).encode()
    requete = Request(
        TOKEN_URL,
        data=donnees,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(requete, timeout=30) as reponse:
            corps = json.loads(reponse.read().decode())
            print(f"[OK] {etiquette} -> token obtenu")
            return corps["access_token"]
    except HTTPError as e:
        corps = e.read().decode(errors="replace")
        print(f"[ECHEC] {etiquette} -> HTTP {e.code} : {corps[:300]}")
        return None
    except URLError as e:
        print(f"[ECHEC] {etiquette} -> connexion : {e}")
        return None


VARIANTES = [
    ("fix support (2 scopes)",
     f"application_{CLIENT_ID} api_stats-offres-demandes-emploiv1 offresetdemandesemploi"),
    ("ancien scope seul (référence)",
     f"application_{CLIENT_ID} api_stats-offres-demandes-emploiv1"),
    ("nouveau scope seul",
     "offresetdemandesemploi"),
    ("sans application_ prefix",
     f"{CLIENT_ID} api_stats-offres-demandes-emploiv1 offresetdemandesemploi"),
]


def main() -> None:
    print("=" * 60)
    print("Test API Marché du Travail — France Travail (INC2760848)")
    print("=" * 60)
    print(f"CLIENT_ID chargé : {CLIENT_ID[:6]}... (longueur {len(CLIENT_ID)})")
    print(f"CLIENT_SECRET chargé : (longueur {len(CLIENT_SECRET)})\n")

    token = None
    for etiquette, scope in VARIANTES:
        print(f"--- Variante : {etiquette} ---")
        print(f"    scope = {scope if 'application_' not in scope else 'application_*** ' + ' '.join(scope.split()[1:])}")
        token = tester_token(scope, etiquette)
        if token:
            break
        print()

    if not token:
        print("\n>>> AUCUNE variante ne passe : coller TOUTE cette sortie dans le chat.")
        print(">>> (les longueurs CLIENT_ID/SECRET aident à vérifier que le .env est bien lu)")
        return

    print("\n--- Appels API avec le scope gagnant ---")
    for ressource in RESSOURCES_A_TESTER:
        tester_ressource(token, ressource)
    print("\n>>> Coller TOUTE cette sortie dans le chat.")


if __name__ == "__main__":
    main()