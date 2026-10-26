# -*- coding: utf-8 -*-
"""
08_detail_mobilites.py — Profil détaillé des étudiants accueillis par ville
(source : fichier détail RP « Mobilités scolaires des individus 2023 », INSEE,
page 9004793, 4,18 M observations, 22 variables, téléchargement manuel).

Colonnes confirmées (dictionnaire INSEE mobsco) :
  COMMUNE  : commune de résidence (chef-lieu pour Paris/Lyon/Marseille,
             l'arrondissement est dans la colonne ARM, non utilisée ici)
  DCETUF   : commune du lieu d'études en France (ARM 751xx/6938x/132xx pour
             Paris/Lyon/Marseille, rabattus sur le chef-lieu)
  DCETUE   : commune FRONTIÈRE du lieu d'études (étranger) — hors périmètre
  AGEREV10 : âge en tranches regroupées (10 modalités)
  SEXE     : 1 = homme, 2 = femme
  IPONDI   : poids de l'individu (estimations, décimales à conserver)

Portée méthodologique — le « PENDANT » des études :
  - qui vient étudier dans chaque ville du référentiel (effectif pondéré),
  - structure par sexe et par tranche d'âge (codes AGEREV10 bruts),
  - origine géographique (locale / même département / extérieure),
  - top 5 des communes de provenance.

Le « APRÈS » (taux de retenue des diplômés) nécessite le fichier RP avec
résidence antérieure ; il fait l'objet d'un traitement séparé.

Limites assumées (documentation INSEE) :
  - champ = individus scolarisés de 2 ans et plus (tous niveaux d'enseignement),
    pas le seul enseignement supérieur -> lecture en volume relatif ;
  - exploitation complémentaire : effectifs < 200 = ordres de grandeur ;
  - décimales IPONDI = estimations sondage RP, comportement attendu.

Sortie : data/raw/detail_mobilites_villes.csv (20 villes, non versionné).

Usage :
    python src/extract/08_detail_mobilites.py --inspect   # structure du fichier
    python src/extract/08_detail_mobilites.py --dims      # modalités des dimensions
    python src/extract/08_detail_mobilites.py            # extraction complète
"""

import argparse
import glob
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE, "data", "raw")
SRC_GLOB = os.path.join(RAW_DIR, "detail_mobilites_scolaires_2023*.csv")
REF_PATH = os.path.join(RAW_DIR, "referentiel_villes.csv")
OUT_PATH = os.path.join(RAW_DIR, "detail_mobilites_villes.csv")

# Arrondissements municipaux (ARM) côté lieu d'études -> chef-lieu.
ARM_MAP = {
    "75": ("75056", "751"),
    "69": ("69123", "6938"),
    "13": ("13055", "132"),
}


def norm_etudes(code: str) -> str:
    """Rabat les ARM du lieu d'études sur la commune chef-lieu."""
    code = str(code).strip()
    if not code or not code.isdigit():
        return ""
    code = code.zfill(5)
    for chef, prefixe in ARM_MAP.values():
        if code.startswith(prefixe):
            return chef
    return code


def find_file():
    hits = sorted(glob.glob(SRC_GLOB))
    if not hits:
        sys.exit(
            "[ERREUR] Fichier source introuvable dans data/raw/.\n"
            "Attendu : detail_mobilites_scolaires_2023*.csv (fichier détail RP\n"
            "« Mobilités scolaires des individus 2023 », page INSEE 9004793)."
        )
    return hits[0]


def read_source(path: str, usecols=None) -> pd.DataFrame:
    """Lecture robuste : séparateur et encodage détectés sur les premières octets."""
    with open(path, "rb") as f:
        head = f.read(4096)
    try:
        head.decode("utf-8")
        enc = "utf-8-sig"
    except UnicodeDecodeError:
        enc = "latin-1"
    sep = "|" if head[:2000].count(b"|") > 5 else ("," if head[:2000].count(b",") > 5 else ";")
    try:
        df = pd.read_csv(path, sep=sep, encoding=enc, dtype=str, usecols=usecols,
                         low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=sep, encoding="latin-1", dtype=str,
                         usecols=usecols, low_memory=False)
    return df


def check_columns(df: pd.DataFrame):
    """Colonnes minimales requises pour l'extraction."""
    requis = ["COMMUNE", "DCETUF", "IPONDI", "SEXE"]
    manquants = [c for c in requis if c not in df.columns]
    if manquants:
        sys.exit(f"[ERREUR] Colonnes absentes du fichier : {manquants}. "
                 f"Colonnes présentes : {sorted(df.columns)}")


def inspect(path: str):
    df = read_source(path)
    check_columns(df)
    print(f"Fichier : {os.path.basename(path)}")
    print(f"Dimensions : {df.shape[0]:,} lignes x {df.shape[1]} colonnes")
    print("\nColonnes (nom — nb de valeurs distinctes) :")
    for c in df.columns:
        print(f"  {c:<12} {df[c].nunique(dropna=True):>10,} distinctes")
    # Contrôles de plausibilité géographiques
    etu = df["DCETUF"].dropna().astype(str).str.zfill(5)
    arm_etu = etu.str.startswith(("751", "6938", "132")).sum()
    res = df["COMMUNE"].dropna().astype(str).str.zfill(5)
    arm_res = res.isin(["75056", "69123", "13055"]).sum()
    print(f"\n[lieu d'études] {etu.nunique():,} communes distinctes ; "
          f"{arm_etu:,} lignes en ARM (Paris/Lyon/Marseille attendus).")
    print(f"[résidence] {res.nunique():,} communes distinctes ; "
          f"{arm_res:,} lignes dans les 3 chefs-lieu ARM.")
    pond = pd.to_numeric(df["IPONDI"], errors="coerce")
    print(f"[pondération] somme={pond.sum():,.0f} ; valeurs invalides={pond.isna().sum():,}")
    # Cohérence avec le champ documenté (population scolarisée 2 ans et +)
    print("[champ] population scolarisée 2 ans et plus (tous niveaux), "
          "France métropolitaine + DOM.")


def dims(path: str):
    """Modalités des dimensions d'analyse (âge, diplôme, lieu d'études typologie)."""
    cols = ["COMMUNE", "DCETUF", "AGEREV10", "SEXE", "DIPL", "ILETUD",
            "ILETUU", "GSM", "DEROU", "IPONDI"]
    df = read_source(path, usecols=cols)
    # Pondération numérique AVANT toute agrégation (sinon somme de chaînes).
    df["poids"] = pd.to_numeric(df["IPONDI"], errors="coerce").fillna(0.0)
    poids_total = df["poids"].sum()
    for c in ["AGEREV10", "SEXE", "DIPL", "ILETUD", "ILETUU", "GSM", "DEROU"]:
        print(f"\n[{c}] modalités (code — effectif pondéré — part %) :")
        for code, w in df.groupby(c)["poids"].sum() \
                .sort_values(ascending=False).items():
            print(f"  {str(code):<6} {w:>14,.0f}  {w / poids_total * 100:5.1f} %")
    # Lyon (bassin universitaire) : structure d'âge des accueillis
    etu = df["DCETUF"].astype(str).str.zfill(5)
    lyon = df[etu.isin(["69123"] + [str(c) for c in range(69381, 69390)])]
    print(f"\n[Lyon — accueillis] {len(lyon):,} lignes ; "
          f"répartition AGEREV10 (pondérée) :")
    tot = lyon["poids"].sum()
    for code, w in (lyon.groupby("AGEREV10")["poids"].sum()
                    .sort_values(ascending=False).items()):
        print(f"  {str(code):<6} {w:>12,.0f}  {w / tot * 100:5.1f} %")


def run():
    path = find_file()
    df = read_source(path)
    check_columns(df)

    if not os.path.exists(REF_PATH):
        sys.exit("[ERREUR] Référentiel des villes manquant : data/raw/referentiel_villes.csv "
                 "(lancer src/extract/06_api_geo.py).")
    ref = pd.read_csv(REF_PATH, dtype={"code_insee": str})
    ref["code_insee"] = ref["code_insee"].str.zfill(5)

    # Normalisation et pondération
    df["res_norm"] = df["COMMUNE"].astype(str).str.zfill(5)
    df["etu_norm"] = df["DCETUF"].map(norm_etudes)
    df["poids"] = pd.to_numeric(df["IPONDI"], errors="coerce").fillna(0.0)
    est_femme = df["SEXE"].astype(str).str.strip() == "2"

    # Tranches d'âge AGEREV10 (libellés confirmés par la distribution nationale
    # et par la structure du bassin de Lyon, dominé par les 18-24 ans).
    AGE_LABELS = {
        "02": "02_02", "03": "03_03", "04": "04_04", "05": "05_05",
        "06": "06_10", "11": "11_14", "15": "15_17", "18": "18_24",
        "25": "25_29", "30": "30_plus",
    }

    rows = []
    for _, r in ref.iterrows():
        code = r["code_insee"]
        acc = df[df["etu_norm"] == code].copy()
        if acc.empty:
            print(f"[AVERTISSEMENT] {r['ville']} : aucune ligne lieu d'études={code}.")
            continue
        w = acc["poids"]
        tot = w.sum()
        dep_ville = code[:2]

        # Origine géographique des accueillis
        meme_commune = acc["res_norm"] == code
        meme_dep = (acc["res_norm"].str[:2] == dep_ville) & ~meme_commune
        autre = ~(meme_commune | meme_dep)
        part_locaux = w[meme_commune].sum() / tot * 100
        part_meme_dep = w[meme_dep].sum() / tot * 100
        part_exterieur = w[autre].sum() / tot * 100

        # Top 5 provenances (hors résidents de la ville elle-même), codes INSEE
        prov = (acc[~meme_commune]
                .groupby("res_norm")["poids"].sum()
                .sort_values(ascending=False))
        top5 = " | ".join(
            f"{c} ({w_:,.0f})".replace(",", " ") for c, w_ in prov.head(5).items())

        row = {
            "ville": r["ville"],
            "code_insee": code,
            "etudiants_accueillis": round(tot, 1),
            "part_femmes": round(w[est_femme.reindex(w.index)].sum() / tot * 100, 1),
            "part_locaux": round(part_locaux, 1),
            "part_meme_dep": round(part_meme_dep, 1),
            "part_exterieur": round(part_exterieur, 1),
            "top5_provenances": top5,
        }
        # Parts par tranche d'âge AGEREV10
        age_code = acc["AGEREV10"].astype(str)
        for code_age, label in AGE_LABELS.items():
            wc = w[age_code == code_age].sum()
            row[f"part_age_{label}"] = round(wc / tot * 100, 1)
        # Indicateur principal : accueillis en âge d'études supérieures (18-24)
        # + agrégats supérieurs (25+) pour la formation continue/doctorats.
        w_1824 = w[age_code == "18"].sum()
        w_25p = w[age_code.isin(["25", "30"])].sum()
        row["part_18_24"] = round(w_1824 / tot * 100, 1)
        row["accueillis_18_24"] = round(w_1824, 1)
        row["part_25_plus"] = round(w_25p / tot * 100, 1)
        rows.append(row)

    out = pd.DataFrame(rows).sort_values("etudiants_accueillis", ascending=False)
    out.to_csv(OUT_PATH, index=False)

    print(f"\nSortie : {os.path.relpath(OUT_PATH, BASE)} — {len(out)}/20 villes.")
    cols_show = ["ville", "etudiants_accueillis", "accueillis_18_24",
                 "part_18_24", "part_femmes", "part_exterieur"]
    with pd.option_context("display.width", 160):
        print(out[cols_show].to_string(index=False))
    top = out.iloc[0]
    print(f"\nVille accueillant la plus d'étudiants (champ scolarisé 2 ans+) : "
          f"{top['ville']} ({top['etudiants_accueillis']:,.0f}) — "
          f"Paris/Lyon attendus en tête.")
    print("Indicateur principal : accueillis_18_24 / part_18_24 "
          "(population scolarisée 18-24 ans, proxy enseignement supérieur).")
    print("Rappel méthodo : le champ couvre toute la population scolarisée "
          "(tous niveaux), pas le seul enseignement supérieur ; "
          "les écarts entre villes se lisent en volume relatif.")
    print("Effectifs décimaux = estimations pondérées (échantillon RP), "
          "comportement attendu.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inspect", action="store_true",
                    help="afficher la structure du fichier source et sortir")
    ap.add_argument("--dims", action="store_true",
                    help="afficher les modalités des dimensions (âge, diplôme, etc.)")
    args = ap.parse_args()
    if args.inspect:
        inspect(find_file())
    elif args.dims:
        dims(find_file())
    else:
        run()


if __name__ == "__main__":
    main()