#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
03_melodi_emploi.py — Pilier EMPLOI via l'API MELODI (INSEE, sans clé).

Extrait pour les 20 villes du référentiel :
  - taux de chômage au lieu de résidence (RP : chômeurs / actifs)
  - (optionnel) taux d'emploi si le jeu de données le fournit directement

Réutilise le gabarit de 02_melodi.py — pièges déjà résolus :
  * ARM : Paris (75) et Lyon (69) diffusés par arrondissements municipaux
    -> fetch DEP-{dep}*COM  +  fetch DEP-{dep}*ARM (le "DEP-{dep}*" seul -> HTTP 500)
  * filtres de dimensions À LA SOURCE dans l'URL (sinon plafond 100 000
    résultats de l'API -> 400 sur les gros départements)
  * pagination : totalCount=TRUE&maxResult=0 -> paging.count, puis maxResult=count
  * 429 -> pause 10 s et retry ; sleep 2,5 s entre requêtes (limite 30 req/min)

⚠️ L'identifiant du jeu "chômage / TACT" n'est PAS encore confirmé.
   Déroulé en 3 étapes :
   1) python src/extract/03_melodi_emploi.py --catalog-emploi
      -> filtre data/raw/melodi_catalogue.json sur emploi/travail/chômage/TACT
      -> coller la sortie dans le chat pour choisir le dataset
   2) python src/extract/03_melodi_emploi.py --dims <ID_DATASET>
      -> inspecte Lyon (ARM inclus), affiche les codes des dimensions
      -> valider avec moi les codes chômeurs / actifs occupés
   3) python src/extract/03_melodi_emploi.py            (run complet)
      -> data/raw/emploi_melodi.csv (ville, code_insee, taux_chomage, n_actifs, ...)
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# ----------------------------------------------------------------------
# CONFIG — à ajuster après les étapes --catalog-emploi / --dims
# ----------------------------------------------------------------------
BASE = "https://api.insee.fr/melodi/data"
ROOT = Path(__file__).resolve().parents[2]
REF_CSV = ROOT / "data" / "raw" / "referentiel_villes.csv"
CATALOG_JSON = ROOT / "data" / "raw" / "melodi_catalogue.json"
OUT_CSV = ROOT / "data" / "raw" / "emploi_melodi.csv"

# Jeu de données CONFIRMÉ (--dims, 16/10/2026) :
DATASET_EMPLOI = "DS_RP_EMPLOI_LR_PRINC"

# Codes des modalités — VALIDÉS via --dims sur Lyon (RP 2023) :
# EMPSTA_ENQ : 1T2 = population active (1 actif occupé + 2 chômeur), 2 = chômeurs
TACT_ACTIFS = "1T2"      # actifs (1T2) — fourni directement par l'API
TACT_CHO = "2"           # chômeurs
SEX_TOT = "_T"
EDUC_TOT = "_T"
AGE_BASE = "Y15T64"      # pas de AGE=_T sur ce jeu ; Y15T64 = tranche marché du travail
MILLESIME = "2023"       # TIME_PERIOD du RP

# Villes avec arrondissements municipaux
ARM_DEPS = {"75": "Paris", "69": "Lyon"}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "edu-move/0.1 (melodi emploi)"})


# ----------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------
def load_referentiel() -> pd.DataFrame:
    if not REF_CSV.exists():
        sys.exit(f"Référentiel introuvable : {REF_CSV} — lancer 06_api_geo.py d'abord.")
    ref = pd.read_csv(REF_CSV, dtype={"code_insee": str})
    # normaliser les noms de colonnes (dep/region parfois absents selon version)
    ref.columns = [c.strip().lower() for c in ref.columns]
    if "code_insee" in ref and ref["code_insee"].str.len().eq(4).all():
        pass  # déjà padding 5 -> non : INSEE commune = 5 chiffres
    return ref


def melodi_get(dataset: str, params: dict, label: str = "") -> list[dict]:
    """GET paginé sur MELODI. Retourne la liste des observations."""
    url = f"{BASE}/{dataset}"
    # ⚠️ Ce jeu ne supporte PAS le paramètre "offset" (HTTP 400).
    # Stratégie (comme 02_melodi.py) : 1er appel avec maxResult=0 pour avoir
    # le count, puis un seul appel avec maxResult=count (tout en 1 page).
    base = dict(params)
    base["totalCount"] = "TRUE"
    base["maxResult"] = "0"
    r = SESSION.get(url, params=base, timeout=120)
    if r.status_code == 429:
        time.sleep(10)
        r = SESSION.get(url, params=base, timeout=120)
    if r.status_code != 200:
        sys.exit(f"  ✗ HTTP {r.status_code} sur {dataset} ({label}, count) : {r.text[:300]}")
    data = r.json()
    paging = data.get("paging") or data.get("_embedded", {}).get("paging") or {}
    total = int(paging.get("count", 0) or 0)
    if not total:
        return []
    time.sleep(2.5)
    p = dict(params)
    p["maxResult"] = str(total)     # tout en 1 page, sans offset
    for attempt in range(4):
        r = SESSION.get(url, params=p, timeout=120)
        if r.status_code == 429:
            print(f"  429 (limite 30 req/min), pause 10 s… ({label})")
            time.sleep(10)
            continue
        break
    if r.status_code != 200:
        sys.exit(f"  ✗ HTTP {r.status_code} sur {dataset} ({label}, data) : {r.text[:300]}")
    obs = r.json().get("observations") or []
    time.sleep(2.5)
    return obs


def fetch_dep(dep: str, dataset: str, extra: dict, label: str) -> list[dict]:
    """Fetch d'un département : communes + ARM si 75/69."""
    out = []
    q = dict(extra)
    q["GEO"] = f"DEP-{dep}*COM"
    out += melodi_get(dataset, q, f"{label} COM")
    if dep in ARM_DEPS:
        q2 = dict(extra)
        q2["GEO"] = f"DEP-{dep}*ARM"
        out += melodi_get(dataset, q2, f"{label} ARM")
    return out


def norm_insee(code: str) -> str:
    """'2026-ARM-69381' / '2026-COM-01259' / '69381' -> code INSEE 5 chiffres."""
    c = str(code).strip()
    if "-" in c:
        c = c.split("-")[-1]
    c = c.lstrip("0") or "0"
    return c.zfill(5)


def to_frame(obs: list[dict]) -> pd.DataFrame:
    rows = []
    for o in obs:
        dims = o.get("dimensions", {}) or {}
        meas = o.get("measures", {}) or {}
        val = None
        for m in meas.values():
            if isinstance(m, dict):
                val = m.get("value")
                break
        if val is None and "OBS_VALUE_NIVEAU" in meas:
            val = meas["OBS_VALUE_NIVEAU"]
        rows.append({**dims, "VALEUR": val})
    return pd.DataFrame(rows)


def rows_to_obs(df: pd.DataFrame, obs: list[dict]):
    """Empile des observations (récupérées par fetch_dep) sans transformation."""
    obs.extend(df.to_dict("records"))


# ----------------------------------------------------------------------
# Étape 1 : filtrer le catalogue sur les jeux emploi/travail
# ----------------------------------------------------------------------
def catalog_emploi():
    if not CATALOG_JSON.exists():
        sys.exit(f"Catalogue introuvable : {CATALOG_JSON} — lancer 02_melodi.py --catalog d'abord.")
    cat = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    items = cat if isinstance(cat, list) else cat.get("datasets") or cat.get("items") or []
    keys = ("emploi", "travail", "chomage", "chôm", "tact", "actif", "activit")
    print(f"Catalogue chargé : {len(items)} jeux. Correspondances emploi/travail :\n")
    for it in items:
        ident = it.get("id") or it.get("datasetId") or it.get("identifier") or ""
        txt = json.dumps(it, ensure_ascii=False).lower()
        if any(k in txt for k in keys):
            name = it.get("name") or it.get("label") or it.get("title") or ""
            n = it.get("nbObservations") or it.get("observationsCount") or "?"
            print(f"  {ident}  |  {n} lignes  |  {name[:90]}")
    print("\n-> Coller cette liste dans le chat : on choisit le dataset TACT/taux de chômage.")


# ----------------------------------------------------------------------
# Étape 2 : --dims — inspecter Lyon
# ----------------------------------------------------------------------
def dims_inspect(dataset: str):
    ref = load_referentiel()
    lyon = ref[ref["ville"].str.lower().str.contains("lyon")].iloc[0]
    dep = str(lyon.get("dep") or lyon["code_insee"][:2]).zfill(2)
    print(f"Inspect {dataset} — Lyon (dep {dep})\n")
    extra = {"SEX": SEX_TOT}
    obs = fetch_dep(dep, dataset, extra, "LYON")
    print(f"Observations : {len(obs)}")
    df = pd.DataFrame([{**(o.get("dimensions") or {}), "VALEUR": _first_val(o)} for o in obs])
    if df.empty:
        sys.exit("Aucune observation — vérifier l'identifiant du dataset (étape --catalog-emploi).")
    for col in [c for c in df.columns if c != "VALEUR"]:
        vals = df[col].dropna().unique()
        print(f"\n[{col}] ({len(vals)} modalités)")
        for v in sorted(map(str, vals))[:40]:
            sub = df[df[col].astype(str) == v]
            print(f"   {v:24s} n={len(sub)}  somme={pd.to_numeric(sub['VALEUR'], errors='coerce').sum():.0f}")
    print("\n-> Coller cette sortie dans le chat pour valider les codes chômeurs / actifs occupés.")
    out = ROOT / "data" / "raw" / f"emploi_dims_{dataset}.json"
    out.write_text(json.dumps(obs[:2000], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Échantillon sauvegardé : {out}")


def _first_val(o: dict):
    for m in (o.get("measures") or {}).values():
        if isinstance(m, dict):
            return m.get("value")
    return None


# ----------------------------------------------------------------------
# Étape 3 : run complet
# ----------------------------------------------------------------------
def run_full():
    if DATASET_EMPLOI in ("", "A_CONFIRMER"):
        sys.exit("DATASET_EMPLOI à confirmer — étapes --catalog-emploi puis --dims d'abord.")
    ref = load_referentiel()
    villes = ref["ville"].tolist()
    print(f"Run complet — {len(villes)} villes, dataset {DATASET_EMPLOI}\n")

    results = []
    for _, row in ref.iterrows():
        ville = row["ville"]
        code = str(row["code_insee"]).zfill(5)
        dep = str(row.get("dep") or code[:2]).zfill(2)
        extra = {"SEX": SEX_TOT, "EDUC": EDUC_TOT, "AGE": AGE_BASE,
                 "TIME_PERIOD": MILLESIME}
        obs = fetch_dep(dep, DATASET_EMPLOI, extra, ville)
        df = to_frame(obs)
        if df.empty:
            print(f"  ⚠ {ville} : 0 observation")
            results.append({"ville": ville, "code_insee": code, "taux_chomage": None})
            continue
        df["CODE"] = df["GEO"].map(norm_insee)
        # commune + ses éventuels ARM (même code pour Paris/Lyon)
        df_v = df[df["CODE"].str.startswith(code)].copy()
        tact_col = next((c for c in ("EMPSTA_ENQ", "TACT", "SIT_TRAV", "STATUT")
                         if c in df.columns), None)
        if tact_col is None:
            sys.exit(f"Colonne statut introuvable. Colonnes vues : {list(df.columns)}")
        g = df_v.groupby(tact_col)["VALEUR"].sum(min_count=1)

        actifs = float(g[TACT_ACTIFS]) if TACT_ACTIFS in g.index else None
        chomeurs = float(g[TACT_CHO]) if TACT_CHO in g.index else None
        taux = round(100 * chomeurs / actifs, 2) if chomeurs and actifs else None
        results.append({"ville": ville, "code_insee": code, "taux_chomage": taux,
                        "chomeurs": chomeurs, "actifs": actifs, "millesime": MILLESIME})
        print(f"  ✓ {ville:18s} chômage {taux if taux is not None else '—'} %  (actifs {actifs})")

    out = pd.DataFrame(results)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"\n✅ Écrit : {OUT_CSV}  ({out['taux_chomage'].notna().sum()}/{len(out)} villes)")


# ----------------------------------------------------------------------
if __name__ == "__main__":
    if "--catalog-emploi" in sys.argv:
        catalog_emploi()
    elif "--dims" in sys.argv:
        i = sys.argv.index("--dims")
        dims_inspect(sys.argv[i + 1] if len(sys.argv) > i + 1 else DATASET_EMPLOI)
    else:
        run_full()