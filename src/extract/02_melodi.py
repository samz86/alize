"""
02_melodi.py — Extraction RP INSEE via API MELODI (20 villes).

Sortie : data/raw/rp_insee.csv
Colonnes : code_insee, ville, annee_rp,
           pop_totale, pop_15_24, part_15_24,
           pop_15plus, pop_dipl_sup, part_dipl_sup,
           pop_active, pop_cadres, part_cadres, part_prof_interm

MELODI : sans clé, limite 30 req/min -> sleep 2,5 s entre requêtes.
Filtres GEO : DEP-{dep}*COM (communes) + DEP-{dep}*ARM (arrondissements
municipaux de Paris/Lyon). NB : DEP-{dep}* seul fait planter le serveur (500).
Filtres de dimensions (SEX, AGE...) appliqués À LA SOURCE : l'API plafonne
à 100 000 résultats par requête -> sans ça, les gros départements échouent.

Usage :
    python src/extract/02_melodi.py --catalog   # lister les jeux RP du catalogue
    python src/extract/02_melodi.py --dims     # dimensions des jeux (Lyon)
    python src/extract/02_melodi.py             # extraction complète
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.insee.fr/melodi"
RAW = Path("data/raw")
RAW.mkdir(parents=True, exist_ok=True)

# Jeux identifiés via --catalog le 15/10/2026 (145 jeux au catalogue MELODI)
DS_AGE = "DS_RP_POPULATION_PRINC"              # Évolution et structure de la population
DS_DIPLO = "DS_RP_DIPLOMES_PRINC"              # Diplômes et Formation - princ. indicateurs
DS_PCS = "DS_RP_TD_POPULATION_PCSAGESEX_COMP"  # Population selon l'âge et la PCS (POP6)

TIMEOUT = 120
SLEEP = 2.5
HEADERS = {"Accept": "application/json"}

VILLES = {
    "Paris": "75056", "Lyon": "69381", "Toulouse": "31555", "Lille": "59350",
    "Bordeaux": "33063", "Nantes": "44109", "Montpellier": "34172",
    "Rennes": "35238", "Strasbourg": "67482", "Grenoble": "38185",
    "Aix-en-Provence": "13001", "Nancy": "54395", "Poitiers": "86194",
    "Tours": "37261", "Clermont-Ferrand": "63113", "Caen": "14118",
    "Nice": "06088", "Reims": "51454", "Angers": "49007", "Dijon": "21231",
}


def http_get(url: str, params: dict | None = None) -> requests.Response:
    """GET avec gestion 429 (limite 30 req/min)."""
    for attempt in range(5):
        r = requests.get(url, params=params, timeout=TIMEOUT,
                         headers=HEADERS)
        if r.status_code == 429:
            print(f"    429 — pause 10 s, essai {attempt + 1}/5")
            time.sleep(10)
            continue
        return r
    raise RuntimeError(f"429 persistant : {url}")


def catalog() -> list[dict]:
    """Liste tous les jeux de données (endpoint du package R : /catalog/all)."""
    r = http_get(f"{BASE}/catalog/all")
    r.raise_for_status()
    return r.json()


def show_catalog():
    """Affiche les jeux RP (et ceux avec résolution communale)."""
    cat = catalog()
    print(f"Catalogue : {len(cat)} jeux de données")
    p = RAW / "melodi_catalogue.json"
    p.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> catalogue complet sauvegardé : {p}\n")
    rp = [c for c in cat if "RP" in str(c.get("identifier", "")).upper()]
    print(f"### Jeux contenant 'RP' : {len(rp)} ###")
    for c in sorted(rp, key=lambda x: x.get("identifier")):
        title = c.get("title") or {}
        if isinstance(title, list):
            title = next((t.get("content") for t in title
                          if isinstance(t, dict) and t.get("lang") == "fr"),
                         str(title))
        print(f"  {c.get('identifier')}  |  {str(title)[:90]}  "
              f"| lignes: {c.get('numObservations')}")


def fetch_dataset(ds: str, geo_filter: str, extra: dict | None = None) -> list[dict]:
    """Récupère toutes les observations d'un jeu avec un filtre GEO.
    extra : filtres de dimensions supplémentaires (ex. SEX=_T, AGE=Y_GE15)
    -> réduit le volume à la source (l'API plafonne à 100 000 résultats)."""
    url = f"{BASE}/data/{ds}"
    extra = extra or {}
    params_count = {"GEO": geo_filter, "totalCount": "TRUE", "maxResult": 0, **extra}
    r = http_get(url, params_count)
    if r.status_code != 200:
        raise RuntimeError(f"{ds} [count {r.status_code}] {r.text[:200]}")
    count = (r.json().get("paging") or {}).get("count", 0)
    print(f"    {ds} GEO={geo_filter} {extra or ''} -> {count} lignes")
    if count == 0:
        return []

    # Récupère les données (tout en une page si possible, sinon par lots)
    for mr in (min(count, 100000), 10000):
        r = http_get(url, {"GEO": geo_filter, "maxResult": mr, **extra})
        if r.status_code == 200:
            body = r.json()
            print(f"    [OK] maxResult={mr}")
            break
        print(f"    [{r.status_code}] maxResult={mr} -> {r.text[:150]}")
        time.sleep(SLEEP)
    else:
        raise RuntimeError(f"Récupération impossible pour {ds}")

    obs = body.get("observations", [])
    # Pages suivantes éventuelles (curseur offset)
    while len(obs) < count:
        time.sleep(SLEEP)
        r = http_get(url, {"GEO": geo_filter, "maxResult": 10000,
                           "offset": len(obs), **extra})
        r.raise_for_status()
        body = r.json()
        page = body.get("observations", [])
        if not page:
            break
        obs += page
    return obs


def fetch_city(ds: str, dep: str, code: str, extra: dict | None = None) -> list[dict]:
    """Communes du département + arrondissements municipaux (ARM) pour
    Paris/Lyon. NB : le filtre 'DEP-{dep}*' (tous niveaux) fait planter
    le serveur (500) -> on combine *COM et *ARM."""
    obs = fetch_dataset(ds, f"DEP-{dep}*COM", extra)
    if code in ("75056", "69381"):
        try:
            obs += fetch_dataset(ds, f"DEP-{dep}*ARM", extra)
        except Exception as e:
            print(f"    [warn] ARM {dep} : {e}")
    return obs


def obs_to_df(obs: list[dict]) -> pd.DataFrame:
    rows = []
    for o in obs:
        row = dict(o.get("dimensions", {}))
        for m, mv in (o.get("measures") or {}).items():
            val = mv.get("value") if isinstance(mv, dict) else mv
            row[m] = val
        rows.append(row)
    return pd.DataFrame(rows)


def filter_commune(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """Garde les lignes de la ville. Paris/Lyon sont diffusés par
    arrondissements municipaux (ARM : 75101-75120, 69381-69389).
    On somme les arrondissements ; si absents, ligne communale simple."""
    if "GEO" not in df.columns or df.empty:
        return df
    g = df["GEO"].astype(str)

    if code == "75056":   # Paris : ARM 75101-75120
        mask = g.str.match(r"\d{4}-ARM-751\d\d$")
    elif code == "69381":  # Lyon : ARM 69381-69389
        mask = g.str.match(r"\d{4}-ARM-6938\d$")
    else:
        mask = g.str.endswith(f"-{code}")

    out = df[mask]
    if not out.empty:
        return out
    # pas d'arrondissements -> ligne communale simple
    return df[g.str.endswith(f"-{code}")]


def show_dims(ds: str, code: str, ville: str):
    dep = code[:2]
    print(f"\n### {ds} — {ville} (département {dep}) ###")
    obs = fetch_city(ds, dep, code)
    if not obs:
        print("    -> 0 lignes")
        return
    df = obs_to_df(obs)
    dfc = filter_commune(df, code)
    print(f"    {len(dfc)} observations pour la commune")
    if dfc.empty:
        geos = sorted({g for g in df["GEO"].astype(str)})
        suspicious = [g for g in geos if code[:4] in g or code[2:] in g]
        print(f"    [DIAG] codes GEO suspects : {suspicious[:30]}")
        print(f"    [DIAG] 10 derniers codes GEO : {geos[-10:]}")
    dims: dict[str, set] = {}
    for o in obs[:200000]:
        for k, v in o.get("dimensions", {}).items():
            dims.setdefault(k, set()).add(str(v))
    for k, vals in sorted(dims.items()):
        vs = sorted(vals)
        if k == "GEO":
            print(f"  GEO ({len(vs)} valeurs) : {vs[:3]} ... {vs[-2:]}")
            continue
        shown = vs if len(vs) <= 30 else vs[:30] + [f"... (+{len(vs)-30})"]
        print(f"  {k} ({len(vs)} valeurs) : {shown}")
    p = RAW / f"melodi_dims_{ds}_{code}.json"
    p.write_text(json.dumps(dfc.to_dict(orient="records"),
                             ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  -> échantillon commune sauvé : {p}")


def extract_age(dep: str, code: str) -> dict:
    df = obs_to_df(fetch_city(DS_AGE, dep, code, {"SEX": "_T"}))
    df = filter_commune(df, code)
    if df.empty:
        return {}
    annee = df["TIME_PERIOD"].max()
    d = df[df["TIME_PERIOD"] == annee]
    # la ligne AGE='_T' est le total ; ne pas sommer avec les tranches
    pop_tot = d[d["AGE"] == "_T"]["OBS_VALUE_NIVEAU"].sum()
    jeun = d[d["AGE"] == "Y15T24"]["OBS_VALUE_NIVEAU"].sum()
    return {"annee_rp": int(annee), "pop_totale": pop_tot, "pop_15_24": jeun,
            "part_15_24": 100 * jeun / pop_tot if pop_tot else None}


def extract_diplomes(dep: str, code: str) -> dict:
    """EDUC : '_T' = population 15+ ; '500T702_RP' = enseignement supérieur."""
    df = obs_to_df(fetch_city(DS_DIPLO, dep, code, {"SEX": "_T"}))
    df = filter_commune(df, code)
    if df.empty:
        return {}
    annee = df["TIME_PERIOD"].max()
    d = df[df["TIME_PERIOD"] == annee]
    pop15 = d[d["EDUC"] == "_T"]["OBS_VALUE_NIVEAU"].sum()
    sup = d[d["EDUC"] == "500T702_RP"]["OBS_VALUE_NIVEAU"].sum()
    return {"pop_15plus": pop15, "pop_dipl_sup": sup,
            "part_dipl_sup": 100 * sup / pop15 if pop15 else None}


def extract_pcs(dep: str, code: str) -> dict:
    """PCS (groupes INSEE) : 3 = cadres et prof. intellec. sup.,
    4 = professions intermédiaires. Population active = codes 1 à 6
    (7 retraités et 9 autres inactifs exclus).
    Filtre à la source SEX=_T + AGE=Y_GE15 (sinon dépassement du plafond
    100 000 de l'API et double comptage)."""
    df = obs_to_df(fetch_city(DS_PCS, dep, code, {"SEX": "_T", "AGE": "Y_GE15"}))
    df = filter_commune(df, code)
    if df.empty:
        return {}
    annee = df["TIME_PERIOD"].max()
    d = df[df["TIME_PERIOD"] == annee]
    act = d[d["PCS"].isin(["1", "2", "3", "4", "5", "6"])]["OBS_VALUE_NIVEAU"].sum()
    cadres = d[d["PCS"] == "3"]["OBS_VALUE_NIVEAU"].sum()
    pi = d[d["PCS"] == "4"]["OBS_VALUE_NIVEAU"].sum()
    return {"pop_active": act, "pop_cadres": cadres, "pop_prof_interm": pi,
            "part_cadres": 100 * cadres / act if act else None,
            "part_prof_interm": 100 * pi / act if act else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", action="store_true",
                    help="Liste les jeux RP du catalogue et sort.")
    ap.add_argument("--dims", action="store_true",
                    help="Affiche les dimensions des jeux pour Lyon et sort.")
    ap.add_argument("--ville", default="Lyon")
    args = ap.parse_args()

    if args.catalog:
        show_catalog()
        print("\n>>> Colle-moi la liste des jeux RP.")
        return

    code = VILLES.get(args.ville)
    if args.dims:
        for ds in (DS_AGE, DS_DIPLO, DS_PCS):
            try:
                show_dims(ds, code, args.ville)
            except Exception as e:
                print(f"    ERREUR {ds} : {e}")
            time.sleep(SLEEP)
        print("\n>>> Colle-moi cette sortie.")
        return

    rows = []
    for ville, code in VILLES.items():
        dep = code[:2]
        print(f"{ville} ({code}, dép. {dep})...")
        rec = {"code_insee": code, "ville": ville}
        try:
            rec.update(extract_age(dep, code))
            rec.update(extract_diplomes(dep, code))
            rec.update(extract_pcs(dep, code))
        except Exception as e:
            print(f"    ERREUR {ville} : {e}")
        rows.append(rec)

    df = pd.DataFrame(rows)
    out = RAW / "rp_insee.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"\nOK : {out} — {len(df)} lignes")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()