# -*- coding: utf-8 -*-
"""
03_marche_travail.py — Extraction des statistiques emploi via l'API France Travail
« Marché du travail v1 » (stats-offres-demandes-emploi, issue de Data Emploi).

Remplace 03_emploi.py (API Offres d'emploi retirée du catalogue — pivot documenté
dans le journal de bord).

Auth : OAuth2 client_credentials
    scope = "application_{client_id} api_stats-offres-demandes-emploiv1"

Étapes :
    1) python src/extract/03_marche_travail.py --inspect
    2) python src/extract/03_marche_travail.py   (après validation)

Prérequis : .env avec FT_CLIENT_ID / FT_CLIENT_SECRET.
"""

import argparse
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

AUTH = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
BASE = "https://api.francetravail.io/partenaire/stats-offres-demandes-emploi/v1"

VILLE_INSEE = {
    "Paris": "75056", "Lyon": "69123", "Toulouse": "31555", "Lille": "59350",
    "Bordeaux": "33063", "Nantes": "44109", "Montpellier": "34172",
    "Rennes": "35238", "Strasbourg": "67482", "Grenoble": "38185",
    "Aix-en-Provence": "13001", "Nancy": "54395", "Poitiers": "86194",
    "Tours": "37261", "Clermont-Ferrand": "63113", "Caen": "14118",
    "Nice": "06088", "Reims": "51454", "Angers": "49007", "Dijon": "21231",
}


def get_token() -> str:
    load_dotenv(ROOT / ".env")
    cid = (os.getenv("FT_CLIENT_ID") or "").strip()
    sec = (os.getenv("FT_CLIENT_SECRET") or "").strip()
    if not cid or not sec:
        sys.exit("ERREUR : FT_CLIENT_ID / FT_CLIENT_SECRET absents du .env")
    scope = f"application_{cid} api_stats-offres-demandes-emploiv1"
    r = requests.post(
        AUTH,
        data={"grant_type": "client_credentials", "scope": scope},
        auth=(cid, sec),
        timeout=30,
    )
    if r.status_code != 200:
        sys.exit(f"[auth] HTTP {r.status_code} : {r.text[:300]}")
    print("[auth] OK (application_* + api_stats-offres-demandes-emploiv1)")
    return r.json()["access_token"]


def api_get(token: str, path: str, params: dict | None = None) -> tuple[int, str]:
    """GET avec Bearer. Retourne (status, body)."""
    url = BASE.rstrip("/") + path
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, params=params, headers=headers, timeout=60)
    return r.status_code, r.text


def show(tag: str, status: int, body: str, keep: int = 900) -> None:
    print(f"\n=== {tag} -> HTTP {status}")
    print(body[:keep] + ("..." if len(body) > keep else ""))


# --- Mode inspect ---------------------------------------------------------

def inspect(token: str) -> None:
    RAW.mkdir(parents=True, exist_ok=True)

    for path in ["/demandeurs", "/offres", "/territoire", "/salaires",
                 "/embauches", "/perspectives-recrutement",
                 "/referentiel/details-indicateurs"]:
        st, body = api_get(token, path)
        show(f"GET {path} (sans params)", st, body)
        (RAW / f"ft_inspect{path.replace('/', '_')}_bare.json").write_text(
            body[:20000], encoding="utf-8")
        if st == 200:
            print("    *** PASSE ! ***")
        time.sleep(1)

    for path in ["/demandeurs", "/offres", "/territoire"]:
        for params in [
            {"codeTerritoire": "69123"},
            {"codeTerritoire": "69123", "typeTerritoire": "COMMUNE"},
            {"codeFamille": "DEMANDEURS", "codeIndicateur": "DE_1"},
        ]:
            st, body = api_get(token, path, params)
            show(f"GET {path} {params}", st, body)
            time.sleep(1)

    print("\n>>> Colle TOUTE cette sortie dans le chat.")
    print(">>> Réponses brutes aussi dans data/raw/ft_inspect_*.json")


# --- Run complet (à débloquer après inspect) --------------------------------

def run_complet(token: str) -> None:
    sys.exit("\nRun complet : à débloquer après validation du --inspect.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()
    tok = get_token()
    if args.inspect:
        inspect(tok)
    else:
        run_complet(tok)