# -*- coding: utf-8 -*-
"""
09_migrations_residentielles.py — Ancrage des diplômés du supérieur et flux
inter-villes (source : fichier détail RP « Migrations résidentielles des
individus 2023 », localisation commune de résidence / commune de résidence
antérieure, INSEE, téléchargement manuel, fichier volumineux national).

Portée méthodologique — le « APRÈS » des études (KPI signature mobilité) :
  - taux d'ancrage : part des diplômés du supérieur 20-29 ans en emploi résidant dans
    chaque ville qui y résidaient déjà 1 an avant (proxy de retenue) ;
  - arrivées de diplômés du supérieur 20-29 ans en emploi venus d'une autre commune ;
  - matrice 20 x 20 des flux de diplômés du supérieur 20-29 ans en emploi entre les
    villes du panel (« villes éducatrices vs gagnantes »).

Limites assumées (documentation INSEE) :
  - la résidence antérieure est celle 1 an avant l'enquête (et non 5 ans) ;
  - pas de distinction CDI/CDD ni de motif du déménagement dans le RP :
    le statut d'activité et le diplôme servent de proxy (diplômés du
    supérieur 20-29 ans en emploi en emploi, déplacement inter-communes) ;
  - découpage : Paris/Lyon/Marseille diffusés en arrondissements municipaux
    (ARM), rabattus sur les chefs-lieu des deux côtés ;
  - exploitation complémentaire : effectifs < 200 = ordres de grandeur ;
  - les poids IPONDI sont des estimations (décimales normales).

Lecture par morceaux (chunks) : le fichier couvre toute la population et peut
dépasser plusieurs Go ; chaque morceau est filtré avant agrégation.

Sorties (data/raw/, non versionnées) :
  - ancrage_diplomes_villes.csv (indicateurs par ville)
  - matrice_flux_diplomes_20villes.csv (matrice origine -> destination)

Usage :
    python src/extract/09_migrations_residentielles.py --inspect
    python src/extract/09_migrations_residentielles.py --dims
    python src/extract/09_migrations_residentielles.py
"""

import argparse
import glob
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE, "data", "raw")
SRC_GLOB = os.path.join(RAW_DIR, "migrations_residentielles_individus_2023*.csv")
REF_PATH = os.path.join(RAW_DIR, "referentiel_villes.csv")
OUT_VILLES = os.path.join(RAW_DIR, "ancrage_diplomes_villes.csv")
OUT_MATRICE = os.path.join(RAW_DIR, "matrice_flux_diplomes_20villes.csv")

# Rabat des ARM sur les chefs-lieu (résidence et résidence antérieure).
ARM_MAP = {
    "75": ("75056", "751"),
    "69": ("69123", "6938"),
    "13": ("13055", "132"),
}

# --- Paramètres d'analyse (dictionnaire officiel contenu_RP2023_migcom) ---
# Fenêtre d'âge : tranches quinquennales AGEREVQ couvrant 20-29 ans
# (020 = 20-24 ans, 025 = 25-29 ans ; l'âge détaillé n'est pas diffusé,
# la fenêtre retenue est donc 20-29 ans, à documenter dans la méthodo).
AGE_BANDS = ["020", "025"]
AGE_LABEL = "20_29"
# DIPL — diplôme le plus élevé : 108 = BTS/DUT/Deug (bac+2),
# 109 = licence/licence pro/BUT (bac+3-4), 110 = master/grandes écoles (bac+5),
# 111 = doctorat de recherche. Supérieur = bac+2 et plus.
DIPL_SUP = ["108", "109", "110", "111"]
# TACT — type d'activité : 11 = actif ayant un emploi (proxy « après les
# études » ; les étudiants TACT=22 sont exclus pour éviter le biais de
# sédentarité universitaire).
TACT_EMPLOI = ["11"]
CHUNKSIZE = 500_000


def norm_commune(code: str) -> str:
    """Rabat les ARM sur la commune chef-lieu ; sinon code INSEE 5 chiffres."""
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
            "Attendu : migrations_residentielles_individus_2023*.csv\n"
            "(fichier détail RP « Migrations résidentielles des individus 2023 », "
            "version commune de résidence / commune de résidence antérieure, "
            "téléchargement manuel depuis la page INSEE 9004842)."
        )
    return hits[0]


def read_head(path: str, nrows: int) -> pd.DataFrame:
    """Petit échantillon pour l'inspection (séparateur/encodage détectés)."""
    with open(path, "rb") as f:
        head = f.read(4096)
    try:
        head.decode("utf-8")
        enc = "utf-8-sig"
    except UnicodeDecodeError:
        enc = "latin-1"
    sep = "|" if head[:2000].count(b"|") > 5 else ("," if head[:2000].count(b",") > 5 else ";")
    try:
        return pd.read_csv(path, sep=sep, encoding=enc, dtype=str, nrows=nrows,
                           low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=sep, encoding="latin-1", dtype=str,
                           nrows=nrows, low_memory=False)


def resolve(df: pd.DataFrame):
    """Résolution des colonnes géographiques et sociodémographiques."""
    cols = list(df.columns)

    def pick(cands, patterns, label):
        for c in cands:
            if c in cols:
                return c
        for c in cols:
            lc = str(c).lower()
            if any(p in lc for p in patterns):
                return c
        sys.exit(f"[ERREUR] Colonne « {label} » introuvable. "
                 f"Candidats testés : {cands}. Colonnes du fichier : {cols}")

    return {
        "res": pick(["COMMUNE", "DCRES", "CODGEO"], ["commune", "cres", "res_"], "commune de résidence"),
        "rain": pick(["DCRAIN", "DCRAN", "RAIN", "DCRA"], ["rain", "ranant", "anterieur"], "commune de résidence antérieure"),
        # AGEMEN8 = âge de la personne de référence du ménage : à EXCLURE,
        # l'âge de l'individu est en tranches quinquennales (AGEREVQ).
        "age": pick(["AGEREVQ", "AGEREV", "AGEREV10", "AGED"], ["agerev", "aged"], "âge (tranches quinquennales)"),
        "dipl": pick(["DIPL"], ["dipl"], "diplôme"),
        "tact": pick(["TACT", "EMPL", "STAT_ACT"], ["tact"], "statut d'activité"),
        "pond": pick(["IPONDI"], ["ipondi", "pond"], "pondération"),
        "sexe": pick(["SEXE"], ["sexe"], "sexe"),
    }


def inspect(path: str):
    df = read_head(path, 200_000)
    taille = os.path.getsize(path) / 1e9
    print(f"Fichier : {os.path.basename(path)} ({taille:.2f} Go)")
    print(f"Échantillon : {len(df):,} premières lignes")
    print("\nColonnes (nom — nb de valeurs distinctes sur l'échantillon) :")
    for c in df.columns:
        print(f"  {c:<12} {df[c].nunique(dropna=True):>8,} distinctes")
    cols = resolve(df)
    print("\nColonnes résolues :")
    for k, v in cols.items():
        print(f"  {k:<6} -> {v}")
    for k in ("res", "rain"):
        codes = df[cols[k]].dropna().map(norm_commune)
        arm = codes.isin(["75056", "69123", "13055"]).sum()
        print(f"\n[{cols[k]}] {codes.nunique():,} communes distinctes ; "
              f"{arm:,} lignes chefs-lieu ARM sur l'échantillon.")
    print("\nNOTE : le champ couvre toute la population (1 an et plus) ; "
          "la résidence antérieure est celle 1 an avant l'enquête "
          "(convention RP depuis 2011).")


def dims(path: str):
    """Modalités des dimensions (diplôme, activité, âge) sur un échantillon."""
    df = read_head(path, 3_000_000)
    cols = resolve(df)
    df["poids"] = pd.to_numeric(df[cols["pond"]], errors="coerce").fillna(0.0)
    poids_total = df["poids"].sum()
    print(f"Échantillon : {len(df):,} lignes ; poids total {poids_total:,.0f}")
    for cle, label in (("dipl", "DIPL"), ("tact", "statut d'activité"), ("sexe", "SEXE"),
                       ("age", "tranches d'âge quinquennales")):
        col = cols[cle]
        print(f"\n[{col}] modalités (code — effectif pondéré — part %) :")
        for code, w in df.groupby(col)["poids"].sum() \
                .sort_values(ascending=False).items():
            print(f"  {str(code):<6} {w:>16,.0f}  {w / poids_total * 100:5.1f} %")


def run():
    if DIPL_SUP:
        pass
    else:
        sys.exit("[ERREUR] DIPL_SUP vide : codage des diplômes du supérieur non "
                 "figé. Lancer --dims et renseigner la constante DIPL_SUP "
                 "(codes licence et plus) avant l'extraction complète.")
    if not AGE_BANDS:
        sys.exit("[ERREUR] AGE_BANDS vide : codes AGEREVQ des tranches 20-24 et "
                 "25-29 non figés. Lancer --dims et renseigner la constante.")
    if not os.path.exists(REF_PATH):
        sys.exit("[ERREUR] Référentiel des villes manquant : data/raw/referentiel_villes.csv "
                 "(lancer src/extract/06_api_geo.py).")
    ref = pd.read_csv(REF_PATH, dtype={"code_insee": str})
    ref["code_insee"] = ref["code_insee"].str.zfill(5)
    villes = dict(zip(ref["code_insee"], ref["ville"]))

    path = find_file()
    # Résolution des colonnes sur un échantillon, puis lecture par morceaux.
    sample = read_head(path, 100_000)
    cols = resolve(sample)
    usecols = [cols[k] for k in ("res", "rain", "age", "dipl", "tact", "pond")]
    with open(path, "rb") as f:
        head = f.read(4096)
    try:
        head.decode("utf-8")
        enc = "utf-8-sig"
    except UnicodeDecodeError:
        enc = "latin-1"
    sep = "|" if head[:2000].count(b"|") > 5 else ("," if head[:2000].count(b",") > 5 else ";")

    # Accumulateurs
    stats = {code: {"stables": 0.0, "arrivees": 0.0, "total": 0.0} for code in villes}
    matrice = {}  # (origine, destination) -> poids
    n_lignes = 0
    n_movers = 0

    for chunk in pd.read_csv(path, sep=sep, encoding=enc, dtype=str,
                             usecols=usecols, chunksize=CHUNKSIZE,
                             low_memory=False):
        n_lignes += len(chunk)
        chunk["poids"] = pd.to_numeric(chunk[cols["pond"]], errors="coerce").fillna(0.0)
        # Population cible : diplômés du supérieur âgés de 20 à 29 ans
        # (tranches quinquennales AGEREVQ).
        cible = chunk[(chunk[cols["dipl"]].isin(DIPL_SUP)) &
                      (chunk[cols["age"]].astype(str).str.strip().isin(AGE_BANDS)) &
                      (chunk[cols["tact"]].isin(TACT_EMPLOI))]
        if cible.empty:
            continue
        cible = cible.copy()
        cible["res_n"] = cible[cols["res"]].map(norm_commune)
        cible["rain_n"] = cible[cols["rain"]].map(norm_commune)

        # 1) Résidants des villes du panel : ancrage
        residants = cible[cible["res_n"].isin(villes)]
        for code, grp in residants.groupby("res_n"):
            w = grp["poids"]
            memes = grp[grp["rain_n"] == code]["poids"].sum()
            stats[code]["total"] += w.sum()
            stats[code]["stables"] += memes
            stats[code]["arrivees"] += w.sum() - memes

        # 2) Movers inter-villes du panel (origine ET destination dans le panel)
        movers = cible[cible["rain_n"].isin(villes) & cible["res_n"].isin(villes)
                       & (cible["rain_n"] != cible["res_n"])]
        n_movers += len(movers)
        for (o, d), w in movers.groupby(["rain_n", "res_n"])["poids"].sum().items():
            matrice[(o, d)] = matrice.get((o, d), 0.0) + w

    # Sortie 1 : indicateurs par ville
    rows = []
    for code, ville in villes.items():
        s = stats[code]
        total = s["total"]
        if total == 0:
            print(f"[AVERTISSEMENT] {ville} : aucun diplômé sup {AGE_LABEL} "
                  f"résidant — colonnes vides.")
        rows.append({
            "ville": ville,
            "code_insee": code,
            f"diplomes_sup_{AGE_LABEL}": round(total, 1),
            "deja_presents_1an": round(s["stables"], 1),
            "arrivees_1an": round(s["arrivees"], 1),
            "taux_ancrage": round(s["stables"] / total * 100, 1) if total else None,
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_VILLES, index=False)

    # Sortie 2 : matrice origine -> destination
    codes = list(villes)
    mat = pd.DataFrame(0.0, index=codes, columns=codes)
    for (o, d), w in matrice.items():
        mat.loc[o, d] = w
    mat.insert(0, "origine", [villes[c] for c in codes])
    mat.columns = ["origine"] + [villes[c] for c in codes]
    mat.to_csv(OUT_MATRICE, index=False)

    print(f"\nLignes lues : {n_lignes:,} ; movers inter-villes du panel : {n_movers:,}")
    print(f"Sortie 1 : {os.path.relpath(OUT_VILLES, BASE)} — {len(out)}/20 villes.")
    print(f"Sortie 2 : {os.path.relpath(OUT_MATRICE, BASE)} — matrice 20x20.")
    cols_show = ["ville", f"diplomes_sup_{AGE_LABEL}", "taux_ancrage", "arrivees_1an"]
    with pd.option_context("display.width", 160):
        print(out.sort_values("taux_ancrage", ascending=False)[cols_show]
              .to_string(index=False))
    print("\nIndicateurs : taux_ancrage = part des diplômés du supérieur "
          f"{AGE_LABEL} ans résidant dans la ville qui y résidaient "
          "déjà 1 an avant (proxy de retenue ; résidence antérieure = 1 an "
          "avant l'enquête, pas 5 ans ; âge diffusé en tranches quinquennales).")
    print("Effectifs décimaux = estimations pondérées (échantillon RP), "
          "comportement attendu.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inspect", action="store_true",
                    help="afficher la structure du fichier source et sortir")
    ap.add_argument("--dims", action="store_true",
                    help="afficher les modalités (diplôme, activité) sur échantillon")
    args = ap.parse_args()
    if args.inspect:
        inspect(find_file())
    elif args.dims:
        dims(find_file())
    else:
        run()


if __name__ == "__main__":
    main()