"""
Quiz « Quelle ville est faite pour toi ? » — v2 avec dimension géographique
=============================================================================
7 questions + domicile -> profil de pondération des 4 piliers -> top 5
data-driven, AVEC distance domicile -> ville et filtre « rester proche ».

100 % transparent (charte anti-projet-factice) : le quiz ne fait QUE modifier
les poids des piliers du scoring existant (transform/scores.py). Le classement
vient toujours de data/processed/villes_scoring.csv. Les distances sont des
distances géodésiques (haversine) calculées à partir des coordonnées officielles
API Géo stockées dans data/raw/referentiel_villes.csv.

v2 — nouveautés :
- Question 0 : commune de domicile (texte libre) -> résolue via API Géo
  (même pattern que src/extract/06_api_geo.py : recherche par nom puis
  fiche par code avec fields=centre, format GeoJSON [lon, lat]).
- La distance domicile -> chaque ville est AFFICHÉE dans le résultat.
- Si la réponse à la question 7 est « rester pas trop loin de ma famille »,
  le classement est FILTRÉ aux villes à moins de 300 km du domicile.
  S'il reste moins de 3 villes dans le rayon, on les affiche toutes et on
  complète avec les meilleures villes hors rayon (marquées « hors rayon »).
- Si l'API Géo est injoignable ou le domicile introuvable : le quiz CONTINUE
  sans dimension géographique (message explicite — jamais de blocage).

Usage
-----
Interactif :
    python transform/quiz.py
Non-interactif (test / site React) :
    python transform/quiz.py --reponses "B,C,A,B,A,B,C" --domicile "Melun"
Chaque question propose 3 choix (A, B, C). Entrée = passer (neutre).
"""

import argparse
import math
import sys
from pathlib import Path

import pandas as pd
import requests

PROCESSED = Path("data/processed/villes_scoring.csv")
REFERENTIEL = Path("data/raw/referentiel_villes.csv")
RAYON_PROXIMITE = 300  # km — filtre si « rester proche de la famille »

W_DEFAUT = {"logement": 30, "emploi": 25, "demographie": 25, "formation": 20}
PILIERS = list(W_DEFAUT)

QUESTIONS = [
    {
        "cle": "budget",
        "question": "1. Côté argent, ta situation plutôt... ?",
        "choix": {
            "A": ("Serrée : je compte chaque euro", {"logement": +15}),
            "B": ("Ça va, mais je dois faire attention", {"logement": +5, "formation": +5}),
            "C": ("Tranquille : je veux surtout profiter de la ville", {"formation": +5, "demographie": +5}),
        },
    },
    {
        "cle": "ville",
        "question": "2. Tu préfères vivre dans quelle ville ?",
        "choix": {
            "A": ("Une petite ou moyenne ville : on va partout à pied ou à vélo", {"demographie": +10}),
            "B": ("Une grande ville : beaucoup de choses à faire et de monde", {"formation": +10}),
            "C": ("Les deux me vont, l'important c'est que le campus soit vivant", {"demographie": +5, "formation": +5}),
        },
    },
    {
        "cle": "apres",
        "question": "3. Après ton diplôme, tu penses faire quoi ?",
        "choix": {
            "A": ("Rester dans la ville où j'ai étudié et y travailler", {"emploi": +10}),
            "B": ("Partir là où je trouverai le meilleur travail", {"emploi": +5, "formation": +5}),
            "C": ("Je ne sais pas encore, on verra", {}),
        },
    },
    {
        "cle": "soirees",
        "question": "4. À côté des cours, tu cherches quoi ?",
        "choix": {
            "A": ("De l'ambiance : associations, sorties, vie étudiante à fond", {"demographie": +10}),
            "B": ("Du calme : bien étudier dans un cadre agréable", {"logement": +10}),
            "C": ("Un mélange des deux", {"demographie": +5, "logement": +5}),
        },
    },
    {
        "cle": "trajet",
        "question": "5. Trouver un job ou une alternance pendant tes études, pour toi c'est... ?",
        "choix": {
            "A": ("Très important : je veux en trouver facilement sur place", {"emploi": +15}),
            "B": ("Pas nécessaire : je me concentre sur mes études", {"formation": +10}),
            "C": ("Sympa si possible, mais pas indispensable", {"emploi": +5}),
        },
    },
    {
        "cle": "logement",
        "question": "6. Pour toi, le logement idéal c'est... ?",
        "choix": {
            "A": ("Pas cher avant tout : un studio simple me suffit", {"logement": +10}),
            "B": ("Confortable : j'aime avoir un vrai chez-moi agréable", {"logement": +5, "emploi": +5}),
            "C": ("Facile à trouver : je déteste galérer dans les recherches", {"logement": +5, "demographie": +5}),
        },
    },
    {
        "cle": "region",
        "question": "7. Loin de chez toi, ça te dit quoi ?",
        "choix": {
            "A": ("Super : je veux découvrir une nouvelle région", {"formation": +10}),
            "B": ("Bof : je préfère rester pas trop loin de ma famille", {"logement": +5, "demographie": +5}),
            "C": ("Peu importe la distance, je choisis pour mes études", {"formation": +5, "emploi": +5}),
        },
    },
]


# ---------------------------------------------------------------------------
# Géoloc
# ---------------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Distance géodésique en km entre deux points (rayon terrestre 6371 km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geolocaliser(nom_commune: str):
    """Résout une commune par nom via API Géo -> (lat, lon) ou None.
    Même pattern que src/extract/06_api_geo.py v2 :
    recherche par nom puis fiche par code avec fields=centre (GeoJSON [lon, lat])."""
    try:
        r = requests.get(
            "https://geo.api.gouv.fr/communes",
            params={"nom": nom_commune, "fields": "code", "boost": "population", "limit": 5},
            timeout=10,
        )
        r.raise_for_status()
        resultats = r.json()
        if not resultats:
            return None
        code = resultats[0]["code"]
        fiche = requests.get(
            f"https://geo.api.gouv.fr/communes/{code}",
            params={"fields": "centre"},
            timeout=10,
        )
        fiche.raise_for_status()
        coords = (fiche.json().get("centre") or {}).get("coordinates")
        if not coords or len(coords) < 2:
            return None
        return float(coords[1]), float(coords[0])  # [lon, lat] -> (lat, lon)
    except (requests.RequestException, KeyError, ValueError):
        return None


def poser(q: dict) -> str:
    """Pose une question, retourne 'A'/'B'/'C' ou '' (saut).
    Escalade bienveillante : 1re erreur = rappel, 2e = consigne détaillée,
    3e = question sautée automatiquement (le quiz continue, jamais de blocage)."""
    erreurs = 0
    print(f"\n{q['question']}")
    for lettre in ("A", "B", "C"):
        print(f"   {lettre}. {q['choix'][lettre][0]}")
    while True:
        rep = input("Ta réponse (A/B/C, Entrée = passer) : ").strip().upper()
        if rep in ("A", "B", "C", ""):
            return rep
        erreurs += 1
        if erreurs == 1:
            print("   Réponse non reconnue — réponds A, B ou C.")
        elif erreurs == 2:
            print("   Il faut taper la lettre A, B ou C (ou juste appuyer sur Entrée pour passer),")
            print("   puis valider avec la touche Entrée. Exemple : b puis Entrée.")
        else:
            print("   Pas grave — on passe à la suivante. Tu pourras relancer le quiz quand tu veux.")
            return ""


def calculer_poids(reponses: dict):
    """reponses = {cle_question: lettre} -> (dict poids normalisés, nb d'ajouts)."""
    w = dict(W_DEFAUT)
    total_ajouts = 0
    for q in QUESTIONS:
        lettre = reponses.get(q["cle"], "")
        if lettre and lettre in q["choix"]:
            for pilier, pts in q["choix"][lettre][1].items():
                w[pilier] += pts
                total_ajouts += pts
    total = sum(w.values())
    return {p: w[p] / total for p in PILIERS}, total_ajouts


def classement(df: pd.DataFrame, poids: dict) -> pd.DataFrame:
    """Score pondéré par pilier à partir des piliers du CSV (0-100)."""
    out = df[["ville"]].copy()
    out["score_quiz"] = (
        poids["logement"] * df["score_logement"]
        + poids["emploi"] * df["score_emploi"]
        + poids["demographie"] * df["score_demographie"]
        + poids["formation"] * df["score_formation"]
    ).round(1)
    return out.sort_values("score_quiz", ascending=False).reset_index(drop=True)


def afficher_resultat(df, poids, reponses, n_ajouts, dom_latlon=None, filtre_proximite=False):
    print("\n" + "=" * 70)
    print("  RÉSULTAT — TES VILLES IDÉALES")
    print("=" * 70)

    print("\n  Ton profil de pondération :")
    print(f"    {'Pilier':<14}{'Poids':>8}{'(défaut)':>12}")
    for p in PILIERS:
        defaut = W_DEFAUT[p] / 100
        print(f"    {p:<14}{poids[p] * 100:>7.0f}%{defaut * 100:>11.0f}%")
    if n_ajouts == 0:
        print("    (aucune réponse influente -> pondération par défaut du projet)")

    # Classement + distances
    rang = classement(df, poids)
    if dom_latlon:
        dom_lat, dom_lon = dom_latlon
        geo = pd.read_csv(REFERENTIEL)
        coords = dict(zip(geo["ville"], zip(geo["latitude"], geo["longitude"])))
        rang["distance_km"] = rang["ville"].map(
            lambda v: round(haversine(dom_lat, dom_lon, *coords[v])) if v in coords else None
        )
        if filtre_proximite:
            dans_rayon = rang[rang["distance_km"] <= RAYON_PROXIMITE]
            hors_rayon = rang[rang["distance_km"] > RAYON_PROXIMITE]
            n_dans = len(dans_rayon)
            if 0 < n_dans < 3:
                # Trop peu dans le rayon : on complète avec les meilleures hors rayon
                top = pd.concat([dans_rayon, hors_rayon.head(5 - n_dans)])
                note = (f"\n  ℹ️ Ton rayon de {RAYON_PROXIMITE} km ne contient que {n_dans} ville(s) "
                        f"du panel — complété par les meilleures villes hors rayon (marquées *).")
            else:
                top = dans_rayon.head(5)
                note = f"\n  ℹ️ Filtré : uniquement les villes à moins de {RAYON_PROXIMITE} km de chez toi."
        else:
            top = rang.head(5)
            note = ""
        dist_col = True
    else:
        top = rang.head(5)
        note = ""
        dist_col = False

    if note:
        print(note)
    print("\n  Top 5 des villes pour ton profil :")
    for i, (_, r) in enumerate(top.iterrows(), 1):
        ligne = f"    {i}. {r['ville']:<18}{r['score_quiz']:>6}"
        if dist_col:
            etoile = " *" if filtre_proximite and r["distance_km"] > RAYON_PROXIMITE else ""
            ligne += f"   ({int(r['distance_km'])} km de chez toi){etoile}"
        print(ligne)

    print("\n  Les 3 moins adaptées à ton profil :")
    bottom_source = top if filtre_proximite else rang.tail(3).iloc[::-1]
    if filtre_proximite:
        # Cohérence : le bottom vient du top filtré (sinon on afficherait une
        # ville du rayon comme « moins adaptée » alors qu'elle a passé le filtre)
        bottom_source = top.tail(3).iloc[::-1]
        print("    (parmi les villes de ton rayon)")
    for i, (_, r) in enumerate(bottom_source.iterrows(), 1):
        ligne = f"    {i}. {r['ville']:<18}{r['score_quiz']:>6}"
        if dist_col:
            ligne += f"   ({int(r['distance_km'])} km)"
        print(ligne)

    print(
        "\n  ⚠️ Lecture : ce classement est un FILTRE D'AIDE À LA DÉCISION, pas un "
        "verdict. Il combine tes priorités avec le score de chaque ville. "
        "Consulte la fiche complète d'une ville avant tout choix réel."
    )
    print(
        "  Méthodo : piliers issus de villes_scoring.csv (MESR, INSEE MELODI RP 2023, "
        "DVF 2025) ; pondération de départ 30/25/25/20, ajustée par tes réponses."
        + (" Distances : géodésiques (haversine), coordonnées API Géo." if dom_latlon else "")
    )


def quiz_interactif(df: pd.DataFrame):
    print("\n" + "=" * 70)
    print("  QUIZ — QUELLE VILLE EST FAITE POUR TOI ?")
    print("=" * 70)
    print("  7 questions, aucune bonne réponse — seulement TES priorités.")

    # Question 0 : domicile (pour la distance — jamais bloquant)
    dom_latlon = None
    domicile = input("\n0. Ta commune de domicile (ex: Melun — Entrée pour ignorer) : ").strip()
    if domicile:
        print(f"   Localisation de {domicile}...")
        dom_latlon = geolocaliser(domicile)
        if dom_latlon:
            print(f"   ✅ Trouvé (lat {dom_latlon[0]}, lon {dom_latlon[1]})")
        else:
            print("   ⚠️ Commune introuvable ou API injoignable — le quiz continue sans distance.")

    reponses = {}
    for q in QUESTIONS:
        reponses[q["cle"]] = poser(q)

    poids, n_ajouts = calculer_poids(reponses)
    filtre = reponses.get("region") == "B"
    afficher_resultat(df, poids, reponses, n_ajouts, dom_latlon, filtre)

    again = input("\nRefaire le quiz ? (o/N) : ").strip().lower()
    if again == "o":
        quiz_interactif(df)


def main():
    p = argparse.ArgumentParser(description="Quiz — ville idéale (Atlas attractivité étudiante)")
    p.add_argument("--reponses", help='Chaîne de réponses aux 7 questions, ex: "B,C,A,B,A,B,C"')
    p.add_argument("--domicile", help="Commune de domicile (ex: Melun) — active distances et filtre proximité")
    opts = p.parse_args()

    if not PROCESSED.exists():
        sys.exit(f"ERREUR : {PROCESSED} introuvable. Lancer d'abord transform/scores.py.")

    df = pd.read_csv(PROCESSED)
    for col in ["ville", "score_logement", "score_emploi", "score_demographie", "score_formation"]:
        if col not in df.columns:
            sys.exit(f"ERREUR : colonne '{col}' absente de {PROCESSED}. Colonnes : {list(df.columns)}")

    dom_latlon = None
    if opts.domicile:
        dom_latlon = geolocaliser(opts.domicile)
        if not dom_latlon:
            print(f"⚠️ Domicile « {opts.domicile} » introuvable — sans dimension géographique.")

    if opts.reponses:
        lettres = [x.strip().upper() for x in opts.reponses.split(",")]
        if len(lettres) != len(QUESTIONS):
            sys.exit(f"--reponses doit contenir {len(QUESTIONS)} valeurs (une par question).")
        reponses = {q["cle"]: l for q, l in zip(QUESTIONS, lettres)}
        poids, n_ajouts = calculer_poids(reponses)
        filtre = reponses.get("region") == "B"
        afficher_resultat(df, poids, reponses, n_ajouts, dom_latlon, filtre)
    else:
        quiz_interactif(df)


if __name__ == "__main__":
    main()