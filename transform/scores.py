"""
Module scores — Atlas de l'attractivité étudiante (edu-move)
============================================================
Fusionne les 5 CSV de data/raw/, calcule les KPI dérivés, normalise et
produit data/processed/villes_scoring.csv (score global + 4 piliers + rang).

Usage :
    python transform/scores.py --inspect   # liste les colonnes de chaque CSV (à coller dans le chat)
    python transform/scores.py             # run complet

Piliers (poids modifiables dans W ci-dessous) :
    logement   = 0.7 prix_m2(inversé) + 0.3 taux_effort(inversé)
    emploi     = 0.5 chomage(inversé) + 0.3 part_cadres + 0.2 part_prof_interm
    demographie= 0.6 densite_etudiante + 0.4 part_15_24
    formation  = 0.7 effectifs + 0.3 part_dipl_sup
    Global     = 0.30 logement + 0.25 emploi + 0.25 demographie + 0.20 formation
"""

import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
RAW = RACINE / "data" / "raw"
PROCESSED = RACINE / "data" / "processed"

FICHIERS = {
    "referentiel": RAW / "referentiel_villes.csv",
    "mestr": RAW / "mestr_effectifs.csv",
    "rp": RAW / "rp_insee.csv",
    "emploi": RAW / "emploi_melodi.csv",
    "dvf": RAW / "dvf_prix_m2.csv",
}

# --- Alias de colonnes : le premier alias trouvé est utilisé -----------------
ALIAS = {
    "ville": ["ville", "nom_ville", "commune", "libelle"],
    "code_insee": ["code_insee", "code_commune", "insee", "depcom", "codegeo"],
    "effectifs": ["effectif_etudiants", "effectifs", "nb_etudiants", "etudiants",
                  "effectif_total", "total_etudiants"],
    "pop": ["pop_totale", "population", "pop", "pop_municipale", "pmun", "nb_habitants"],
    "part_15_24": ["part_15_24", "part_15_24_ans", "pct_15_24", "part_jeunes"],
    "part_dipl_sup": ["part_dipl_sup", "part_diplomes_sup", "pct_dipl_sup"],
    "part_cadres": ["part_cadres", "part_csp3", "pct_cadres"],
    "part_prof_interm": ["part_prof_interm", "part_csp4", "pct_prof_intermediaires"],
    "taux_chomage": ["taux_chomage", "chomage", "taux_chom", "pct_chomage"],
    "prix_m2": ["prix_m2_median_appart", "prix_m2", "prix_median_m2", "prix_m2_median"],
    "n_transactions": ["n_transactions", "nb_transactions", "transactions"],
}


def charger_csv(nom: str) -> pd.DataFrame:
    chemin = FICHIERS[nom]
    if not chemin.exists():
        sys.exit(f"[ERREUR] Fichier introuvable : {chemin}")
    df = pd.read_csv(chemin, dtype={"code_insee": str})
    # nettoyage basique : strip + unicité code
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()
    return df


def resoudre_colonne(df: pd.DataFrame, cle: str, source: str) -> str:
    """Retourne le nom réel de la colonne pour la clé logique `cle`."""
    for alias in ALIAS[cle]:
        if alias in df.columns:
            return alias
    dispo = ", ".join(df.columns)
    sys.exit(f"[ERREUR] Dans {source} ({FICHIERS[source].name}), aucune colonne "
             f"trouvée pour '{cle}'. Essais : {ALIAS[cle]}. Colonnes dispo : {dispo}")


def inspect() -> None:
    """Mode --inspect : colonnes + 2 lignes de chaque CSV, à coller dans le chat."""
    print("=" * 70)
    for nom, chemin in FICHIERS.items():
        print(f"\n### {nom} -> {chemin.name}")
        if not chemin.exists():
            print("  !! FICHIER INTROUVABLE")
            continue
        df = pd.read_csv(chemin)
        print(f"  lignes: {len(df)}")
        print(f"  colonnes: {list(df.columns)}")
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(df.head(2).to_string(index=False))
    print("\nColler TOUTE cette sortie dans le chat pour validation avant le run complet.")


def run() -> None:
    ref = charger_csv("referentiel")
    mes = charger_csv("mestr")
    rp = charger_csv("rp")
    emp = charger_csv("emploi")
    dvf = charger_csv("dvf")

    # --- 0. Base = référentiel ------------------------------------------------
    c_ref_ville = resoudre_colonne(ref, "ville", "referentiel")
    ref = ref.rename(columns={c_ref_ville: "ville"})
    c_ref_code = resoudre_colonne(ref, "code_insee", "referentiel")
    ref["code_insee"] = ref[c_ref_code].str.zfill(5)
    df = ref[["code_insee", "ville"]].drop_duplicates("code_insee").copy()
    n_attendu = len(df)
    print(f"Référentiel : {n_attendu} villes.")

    # --- 1. Fusion sur code_insee (validate 1:1) ------------------------------
    def joindre(df_base: pd.DataFrame, src: pd.DataFrame, nom: str,
                colonnes: list[str]) -> pd.DataFrame:
        codes = resoudre_colonne(src, "code_insee", nom)
        villes = resoudre_colonne(src, "ville", nom)
        src = src.copy()
        src["code_insee"] = src[codes].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
        garde = ["code_insee"] + [resoudre_colonne(src, c, nom) for c in colonnes]
        src = src[garde + [villes]].drop_duplicates("code_insee")

        out = df_base.merge(src[garde], on="code_insee", how="left", validate="1:1")
        # --- Repli : villes manquées par le code (ex. Lyon ARM 69381 vs 69123) ---
        cle_ville_base = resoudre_colonne(out, "ville", "fusion")
        norm = lambda s: (s.astype(str).str.lower().str.normalize("NFKD")
                          .str.encode("ascii", errors="ignore").str.decode("ascii")
                          .str.replace(r"[^a-z]", "", regex=True))
        manquantes = out[out[garde[1:]].isna().any(axis=1)]
        if len(manquantes):
            src["_ville_norm"] = norm(src[villes])
            src_par_ville = src.drop_duplicates("_ville_norm").set_index("_ville_norm")
            for idx in manquantes.index:
                v = norm(out.loc[[idx], cle_ville_base]).iloc[0]
                if v in src_par_ville.index:
                    for col in garde[1:]:
                        out.loc[idx, col] = src_par_ville.loc[v, col]
                    print(f"  [REPLI] {out.loc[idx, cle_ville_base]} jointée par nom "
                          f"(code_insee source = {src_par_ville.loc[v, 'code_insee']})")
        print(f"  {nom}: {out[garde[1:]].notna().all(axis=1).sum()}/{n_attendu} villes jointées")
        return out

    df = joindre(df, mes, "mestr", ["effectifs"])
    df = joindre(df, rp, "rp", ["pop", "part_15_24", "part_dipl_sup",
                                "part_cadres", "part_prof_interm"])
    df = joindre(df, emp, "emploi", ["taux_chomage"])
    df = joindre(df, dvf, "dvf", ["prix_m2"])

    # renommer vers noms logiques
    df = df.rename(columns={
        resoudre_colonne(df, c, "fusion"): c
        for c in ["effectifs", "pop", "part_15_24", "part_dipl_sup",
                  "part_cadres", "part_prof_interm", "taux_chomage", "prix_m2"]
    })
    for c in ["effectifs", "pop", "part_15_24", "part_dipl_sup", "part_cadres",
              "part_prof_interm", "taux_chomage", "prix_m2"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    manquantes = df[df[["effectifs", "pop", "part_15_24", "part_dipl_sup",
                        "part_cadres", "part_prof_interm", "taux_chomage"]]
                    .isna().any(axis=1)]
    if len(manquantes):
        print(f"[ATTENTION] Valeurs manquantes hors prix_m2 pour : "
              f"{list(manquantes['ville'])}")

    # --- 2. KPI dérivés ---------------------------------------------------------
    df["densite_etudiante"] = 100 * df["effectifs"] / df["pop"]          # étudiants / pop en %
    df["ecart_chomage"] = df["taux_chomage"] - df["taux_chomage"].mean()
    df["prix_m2_diplome"] = df["prix_m2"] / df["part_dipl_sup"]         # éditorial, PAS dans le score
    # Taux d'effort logement (approx documentée) : loyer ≈ 0,5 % de la valeur d'achat / mois
    # studio 20 m², budget étudiant 800 €/mois
    df["loyer_estime"] = 0.005 * df["prix_m2"] * 20
    df["taux_effort_logement"] = 100 * df["loyer_estime"] / 800

    # --- 3. Strasbourg : imputation prix (score uniquement) ---------------------
    prix_affiche = df["prix_m2"].copy()
    stras = df["ville"].str.contains("trasbourg", case=False, na=False)
    if df.loc[stras, "prix_m2"].isna().any():
        mediane_autres = df.loc[~stras, "prix_m2"].median()
        df.loc[stras, "prix_m2"] = mediane_autres
        df.loc[stras, "taux_effort_logement"] = (
            100 * (0.005 * mediane_autres * 20) / 800)
        df.loc[stras, "prix_m2_diplome"] = mediane_autres / df.loc[stras, "part_dipl_sup"]
        print(f"[INFO] Strasbourg : prix_m2 imputé à la médiane des autres villes "
              f"({mediane_autres:.1f} €/m²) POUR LE SCORE UNIQUEMENT — "
              f"KPI prix affiché = vide dans le CSV final.")
    df["prix_m2_affiche"] = prix_affiche

    # --- 4. Normalisation min-max 0-100 (orientée attractivité) -----------------
    def norm(c: pd.Series, inverse: bool = False) -> pd.Series:
        x = (c - c.min()) / (c.max() - c.min())
        if inverse:
            x = 1 - x
        return 100 * x

    df["n_prix"] = norm(df["prix_m2"], inverse=True)
    df["n_effort"] = norm(df["taux_effort_logement"], inverse=True)
    df["n_chomage"] = norm(df["taux_chomage"], inverse=True)
    df["n_cadres"] = norm(df["part_cadres"])
    df["n_prof_interm"] = norm(df["part_prof_interm"])
    df["n_densite"] = norm(df["densite_etudiante"])
    df["n_15_24"] = norm(df["part_15_24"])
    df["n_effectifs"] = norm(df["effectifs"])
    df["n_dipl_sup"] = norm(df["part_dipl_sup"])

    # --- 5. Piliers ---------------------------------------------------------------
    df["score_logement"] = (0.7 * df["n_prix"] + 0.3 * df["n_effort"]).round(1)
    df["score_emploi"] = (0.5 * df["n_chomage"] + 0.3 * df["n_cadres"]
                          + 0.2 * df["n_prof_interm"]).round(1)
    df["score_demographie"] = (0.6 * df["n_densite"] + 0.4 * df["n_15_24"]).round(1)
    df["score_formation"] = (0.7 * df["n_effectifs"] + 0.3 * df["n_dipl_sup"]).round(1)

    W = {"logement": 0.30, "emploi": 0.25, "demographie": 0.25, "formation": 0.20}
    df["score_global"] = (W["logement"] * df["score_logement"]
                          + W["emploi"] * df["score_emploi"]
                          + W["demographie"] * df["score_demographie"]
                          + W["formation"] * df["score_formation"]).round(1)

    df = df.sort_values("score_global", ascending=False).reset_index(drop=True)
    df["rang"] = df.index + 1

    # --- 6. Sortie ------------------------------------------------------------------
    PROCESSED.mkdir(parents=True, exist_ok=True)
    colonnes_out = [
        "rang", "ville", "code_insee", "score_global",
        "score_logement", "score_emploi", "score_demographie", "score_formation",
        # KPI bruts / dérivés
        "effectifs", "pop", "densite_etudiante", "part_15_24", "part_dipl_sup",
        "part_cadres", "part_prof_interm", "taux_chomage", "ecart_chomage",
        "prix_m2", "taux_effort_logement", "prix_m2_diplome",
    ]
    df = df.rename(columns={"prix_m2_affiche": "prix_m2"})
    out = PROCESSED / "villes_scoring.csv"
    df[colonnes_out].to_csv(out, index=False)

    print(f"\n{'='*70}\nSortie : {out}\n{'='*70}")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df[colonnes_out[:8]].to_string(index=False))
    print("\n>>> Coller ce tableau dans le chat pour validation.")


if __name__ == "__main__":
    if "--inspect" in sys.argv:
        inspect()
    else:
        run()