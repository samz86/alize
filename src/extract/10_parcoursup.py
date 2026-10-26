#!/usr/bin/env python
"""
10_parcoursup.py — Alizé : offre de formations Parcoursup par ville.
====================================================================

Source : cartographie des formations Parcoursup (open data MESR),
une ligne par formation accessible via Parcoursup. Session la plus
récente uniquement (2026 au 26/10/2026).

Particularité de la source : la colonne « Types de formation » est
multi-étiquettes (ex. « Etudes de santé,Licence » = 1 formation
comptée dans 2 familles). L'agrégation explose sur la virgule :
le total par famille peut donc dépasser le nombre de formations.
C'est documenté ici et dans les sorties.

Sorties (data/raw/) :
  - parcoursup_villes.csv     : 1 ligne par ville (nb formations,
    nb établissements, part apprentissage, familles présentes)
  - parcoursup_familles.csv   : format long ville x famille x nb

Deux modes :
  --inspect   : examine le fichier brut, ne produit RIEN.
  (défaut)    : agrégation par ville (sorties ci-dessus).

Usage (depuis la racine du dépôt) :
  python src/extract/10_parcoursup.py --inspect
  python src/extract/10_parcoursup.py
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[2]
RAW = RACINE / "data" / "raw"
OUT_VILLES = RACINE / "data" / "processed" / "parcoursup_villes.csv"
OUT_FAMILLES = RACINE / "data" / "processed" / "parcoursup_familles.csv"

# Le fichier téléchargé manuellement depuis data.enseignementsup-recherche.gouv.fr
# (jeu fr-esr-cartographie_formations_parcoursup, export CSV « ; »).
FICHIER = RAW / "parcoursup_formations.csv"

# Référentiel des 20 villes (noms exacts comme dans 06_api_geo.py).
VILLES = [
    "Paris", "Lyon", "Toulouse", "Lille", "Bordeaux", "Nantes",
    "Montpellier", "Rennes", "Strasbourg", "Grenoble", "Aix-en-Provence",
    "Nancy", "Poitiers", "Tours", "Clermont-Ferrand", "Caen", "Nice",
    "Reims", "Angers", "Dijon",
]


def trouver_fichier() -> Path:
    """Retourne le CSV Parcoursup présent dans data/raw/ (nom exact ou glob)."""
    if FICHIER.exists():
        return FICHIER
    candidats = sorted(RAW.glob("*parcoursup*.csv")) if RAW.exists() else []
    if len(candidats) == 1:
        return candidats[0]
    if not candidats:
        sys.exit("Aucun CSV Parcoursup trouvé dans data/raw/. Télécharge l'export depuis\n"
                 "data.enseignementsup-recherche.gouv.fr (cartographie des formations\n"
                 "Parcoursup) et place-le dans data/raw/.")
    sys.exit("Plusieurs candidats trouvés : " + ", ".join(c.name for c in candidats)
             + "\nRenomme le bon en parcoursup_formations.csv.")


def charger(path: Path) -> pd.DataFrame:
    """Charge le CSV (séparateur et encodage détectés)."""
    for sep in [";", ",", "\t"]:
        try:
            df = pd.read_csv(path, sep=sep, encoding="utf-8-sig", low_memory=False,
                             dtype=str)
            if len(df.columns) > 3:
                print(f"Lecture OK : {len(df):,} lignes x {len(df.columns)} colonnes "
                      f"(séparateur '{sep}')")
                return df
        except Exception:
            continue
    sys.exit("Impossible de lire le CSV : séparateur non détecté.")


def col(df: pd.DataFrame, mots_cles: list) -> str | None:
    """Retourne la première colonne dont le nom contient tous les mots-clés
    (insensible à la casse/accents), sinon None."""
    import unicodedata
    def norm(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                       if unicodedata.category(c) != "Mn")
    for c in df.columns:
        cn = norm(c)
        if all(m in cn for m in mots_cles):
            return c
    return None


def inspect(df: pd.DataFrame) -> None:
    """Mode inspection : structure, sessions, couverture des 20 villes."""
    print("\n=== COLONNES ===")
    for i, c in enumerate(df.columns):
        n_na = df[c].isna().sum()
        n_uniq = df[c].nunique(dropna=True)
        print(f"{i:3d}. {c!r}  (vides: {n_na:,}, uniques: {n_uniq:,})")

    print("\n=== COLONNES REPÉRÉES ===")
    hypotheses = [
        (["session"], "session / millésime"),
        (["commune"], "commune de l'établissement"),
        (["types", "formation"], "types de formation (multi-étiquettes)"),
        (["apprentissage"], "apprentissage"),
        (["etablissement"], "identifiant établissement"),
    ]
    for mots, role in hypotheses:
        print(f"  {role:38s} -> {col(df, mots)!r}")

    c_session = col(df, ["session"])
    if c_session:
        print("\n=== SESSIONS DISPONIBLES ===")
        print(df[c_session].value_counts(dropna=False).to_string())

    c_commune = col(df, ["commune"])
    if c_commune:
        print("\n=== COUVERTURE DES 20 VILLES ===")
        communes = df[c_commune].str.strip()
        for v in VILLES:
            n = (communes.str.upper() == v.upper()).sum()
            print(f"  {v:18s} {n:6,} formations "
                  f"{'OK' if n > 0 else 'ABSENT'}")

    c_types = col(df, ["types", "formation"])
    if c_types and c_session:
        df_recent = df[df[c_session] == df[c_session].max()]
        print(f"\n=== VALEURS DE {c_types!r} (session "
              f"{df[c_session].max()}) ===")
        print(df_recent[c_types].value_counts(dropna=False).to_string())

    print("\nInspection terminée. Rien n'a été écrit.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true",
                    help="examiner le fichier sans rien produire")
    args = ap.parse_args()

    path = trouver_fichier()
    print(f"Fichier : {path}")
    df = charger(path)

    if args.inspect:
        inspect(df)
        return

    # ------------------------------------------------------------------
    # Agrégation par ville — session la plus récente uniquement.
    # ------------------------------------------------------------------
    c_session = col(df, ["session"])
    c_commune = col(df, ["commune"])
    c_types = col(df, ["types", "formation"])
    c_apprentissage = col(df, ["apprentissage"])
    c_etab = col(df, ["etablissement"])

    if not (c_session and c_commune and c_types):
        sys.exit("Colonnes Session/Commune/Types de formation introuvables : "
                 "lance --inspect et vérifie la source.")

    session_max = df[c_session].max()
    df = df[df[c_session] == session_max].copy()
    print(f"Session retenue : {session_max} ({len(df):,} formations France entière)")

    # 20 villes uniquement ; communes vides écartées (775 lignes France entière).
    df = df[df[c_commune].notna()]
    df = df[df[c_commune].str.strip().str.upper()
            .isin([v.upper() for v in VILLES])].copy()
    # Noms canoniques du référentiel (évite les fausses casses type
    # « Aix-En-Provence » produites par .title(), qui casseraient la
    # jointure avec les autres sorties du projet).
    canonique = {v.upper(): v for v in VILLES}
    df["ville"] = df[c_commune].str.strip().str.upper().map(canonique)
    print(f"Formations dans les 20 villes : {len(df):,}")

    if df.empty:
        sys.exit("Aucune formation trouvée pour les 20 villes.")

    # Apprentissage : colonne remplie = une voie en apprentissage existe.
    if c_apprentissage:
        valeurs = df[c_apprentissage].dropna().unique()
        print(f"Valeurs apprentissage rencontrées : {valeurs.tolist()}")
        df["est_apprentissage"] = df[c_apprentissage].notna()
    else:
        df["est_apprentissage"] = False

    # Familles : la colonne est multi-étiquettes, on explose sur la virgule.
    # NB : les libellés contiennent des virgules internes ? Non — le
    # séparateur d'étiquettes est la virgule, les libellés observés
    # (BTS - BTSA - BTSM, Etudes de santé, CPGE...) n'en contiennent pas.
    familles = (df[["ville", c_types]]
                .assign(famille=df[c_types].str.split(","))
                .explode("famille"))
    familles["famille"] = familles["famille"].str.strip()
    familles = familles[familles["famille"] != ""]

    long = (familles.groupby(["ville", "famille"]).size()
            .reset_index(name="nb_formations")
            .sort_values(["ville", "nb_formations"],
                         ascending=[True, False]))
    long.to_csv(OUT_FAMILLES, index=False, encoding="utf-8")
    print(f"Écrit : {OUT_FAMILLES} ({len(long)} lignes ville x famille)")
    print("NB : multi-étiquettes — une formation peut compter dans plusieurs "
          "familles (le total par ville dépasse le nombre de formations).")

    resume = (df.groupby("ville")
              .agg(nb_formations=(c_types, "size"),
                   nb_etablissements=(c_etab, "nunique"),
                   nb_voies_apprentissage=("est_apprentissage", "sum"))
              .reset_index())
    familles_ville = long.groupby("ville")["famille"].nunique()
    resume["familles_presentes"] = resume["ville"].map(familles_ville)
    resume["part_apprentissage"] = (100 * resume["nb_voies_apprentissage"]
                                     / resume["nb_formations"]).round(1)
    resume = (resume.sort_values("nb_formations", ascending=False)
              [["ville", "nb_formations", "nb_etablissements",
                "familles_presentes", "nb_voies_apprentissage",
                "part_apprentissage"]])
    resume.to_csv(OUT_VILLES, index=False, encoding="utf-8")
    print(f"Écrit : {OUT_VILLES} ({len(resume)} villes)")
    print(resume.to_string(index=False))
    print("\nContrôles : 20 villes attendues ->", len(resume),
          "| session :", session_max,
          "| multi-étiquettes documentées dans l'en-tête du script.")


if __name__ == "__main__":
    main()