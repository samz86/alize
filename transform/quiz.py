"""
Quiz « Quelle ville est faite pour toi ? » — Atlas de l'attractivité étudiante
=============================================================================
7 questions simples -> profil de pondération des 4 piliers -> top 5 data-driven.

100 % transparent (charte anti-projet-factice) : le quiz ne fait QUE modifier
les poids des piliers du scoring existant (transform/scores.py). Le classement
final vient toujours de data/processed/villes_scoring.csv. Aucune donnée
inventée, aucun biais caché : le poids final est affiché à l'utilisateur.

Usage
-----
Interactif :
    python transform/quiz.py

Non-interactif (test / site React) — réponses en une chaîne, ex. :
    python transform/quiz.py --reponses "B,C,A,B,A,B,C"

Chaque question propose 3 choix (A, B, C). L'utilisateur peut aussi sauter
(Entrée = neutre, aucune influence). 7 questions au total.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

PROCESSED = Path("data/processed/villes_scoring.csv")

# ---------------------------------------------------------------------------
# Poids de départ = pondération officielle du projet (logement 30, emploi 25,
# démo 25, formation 20 — identique à scores.py et simulateur.py).
# Chaque réponse ajoute des points aux piliers concernés, puis on normalise
# pour que la somme fasse 1. Les « points » sont simples et lisibles.
# ---------------------------------------------------------------------------
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


def calculer_poids(reponses: dict) -> dict:
    """reponses = {cle_question: lettre} -> dict de poids normalisés."""
    w = dict(W_DEFAUT)
    total_ajouts = 0
    for q in QUESTIONS:
        lettre = reponses.get(q["cle"], "")
        if lettre and lettre in q["choix"]:
            ajustements = q["choix"][lettre][1]
            for pilier, pts in ajustements.items():
                w[pilier] += pts
                total_ajouts += pts
    # Normalisation : somme = 1 (affichage en % pour la lisibilité)
    total = sum(w.values())
    return {p: w[p] / total for p in PILIERS}, total_ajouts


def classement(df: pd.DataFrame, poids: dict) -> pd.DataFrame:
    """Score pondéré par pilier à partir des piliers du CSV (0-100)."""
    out = pd.DataFrame({"ville": df["ville"]})
    out["score_quiz"] = (
        poids["logement"] * df["score_logement"]
        + poids["emploi"] * df["score_emploi"]
        + poids["demographie"] * df["score_demographie"]
        + poids["formation"] * df["score_formation"]
    ).round(1)
    return out.sort_values("score_quiz", ascending=False).reset_index(drop=True)


def afficher_resultat(df: pd.DataFrame, poids: dict, reponses: dict, n_ajouts: int):
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

    print("\n  Top 5 des villes pour ton profil :")
    top = classement(df, poids).head(5)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        print(f"    {i}. {r['ville']:<18}{r['score_quiz']:>6}")

    print("\n  Les 3 moins adaptées à ton profil :")
    bottom = classement(df, poids).tail(3).iloc[::-1]
    for i, (_, r) in enumerate(bottom.iterrows(), 1):
        print(f"    {i}. {r['ville']:<18}{r['score_quiz']:>6}")

    print(
        "\n  ⚠️ Lecture : ce classement est un FILTRE D'AIDE À LA DÉCISION, pas un "
        "verdict. Il combine tes priorités avec le score de chaque ville. "
        "Consulte la fiche complète d'une ville avant tout choix réel."
    )
    print(
        "  Méthodo : piliers issus de villes_scoring.csv (MESR, INSEE MELODI RP 2023, "
        "DVF 2025) ; pondération de départ 30/25/25/20, ajustée par tes réponses."
    )


def quiz_interactif(df: pd.DataFrame):
    print("\n" + "=" * 70)
    print("  QUIZ — QUELLE VILLE EST FAITE POUR TOI ?")
    print("=" * 70)
    print("  7 questions, aucune bonne réponse — seulement TES priorités.")

    reponses = {}
    for q in QUESTIONS:
        reponses[q["cle"]] = poser(q)

    poids, n_ajouts = calculer_poids(reponses)
    afficher_resultat(df, poids, reponses, n_ajouts)

    again = input("\nRefaire le quiz ? (o/N) : ").strip().lower()
    if again == "o":
        quiz_interactif(df)


def main():
    p = argparse.ArgumentParser(description="Quiz — ville idéale (Atlas attractivité étudiante)")
    p.add_argument("--reponses", help='Chaîne de réponses, ex: "B,C,A,B,A"')
    opts = p.parse_args()

    if not PROCESSED.exists():
        sys.exit(f"ERREUR : {PROCESSED} introuvable. Lancer d'abord transform/scores.py.")

    df = pd.read_csv(PROCESSED)
    for col in ["ville", "score_logement", "score_emploi", "score_demographie", "score_formation"]:
        if col not in df.columns:
            sys.exit(f"ERREUR : colonne '{col}' absente de {PROCESSED}. Colonnes : {list(df.columns)}")

    if opts.reponses:
        lettres = [x.strip().upper() for x in opts.reponses.split(",")]
        if len(lettres) != len(QUESTIONS):
            sys.exit(f"--reponses doit contenir {len(QUESTIONS)} valeurs (une par question).")
        reponses = {q["cle"]: l for q, l in zip(QUESTIONS, lettres)}
        poids, n_ajouts = calculer_poids(reponses)
        print(f"Réponses : {reponses}")
        afficher_resultat(df, poids, reponses, n_ajouts)
    else:
        quiz_interactif(df)


if __name__ == "__main__":
    main()