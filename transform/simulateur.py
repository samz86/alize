"""
Simulateur What-if — Atlas de l'attractivité étudiante
======================================================
Moteur de politiques publiques : "Si l'indicateur X bouge dans la ville Y,
que devient son score et son rang ?"

Fonctionne à partir de data/processed/villes_scoring.csv (produit par
transform/scores.py). Réutilise exactement la même méthodologie :
normalisation min-max 0-100 sur le panel des 20 villes, piliers et poids
identiques (logement 30 / emploi 25 / démographie 25 / formation 20).

Charte honnêteté (charte anti-projet-factice ⑨) :
- Le simulateur ne prétend à AUCUNE causalité. Il traduit un changement
  d'indicateur en variation de score, à méthodologie constante.
- L'élasticité prix-attractivité testée en régression était NON
  significative (n=19) : ce simulateur n'en dérive rien.

Usage
-----
1) Inspecter d'abord (confirmer les noms de colonnes) :
    python transform/simulateur.py --inspect

2) Simulations (une ou plusieurs options par appel, cumulables) :
    python transform/simulateur.py --ville Lyon --prix -10
    python transform/simulateur.py --ville Poitiers --chomage -2
    python transform/simulateur.py --ville Paris --prix -10 --chomage -1.5
    python transform/simulateur.py --ville Rennes --etudiants +5000
    python transform/simulateur.py --ville Dijon --part-cadres +5

3) Comparer toutes les villes sur un scénario (ex: prix -10 % partout) :
    python transform/simulateur.py --ville TOUTES --prix -10

Options de simulation (valeur : % relatif si commence par +/- suivi d'un
nombre, sinon points absolus pour --chomage) :
    --prix P           variation en % du prix m² médian
    --chomage P        variation en POINTS du taux de chômage
    --etudiants N      variation absolue des effectifs étudiants
    --part-cadres P    variation en POINTS de la part de cadres
    --part-15-24 P     variation en POINTS de la part 15-24 ans
    --part-dipl-sup P  variation en POINTS de la part de diplômés du supérieur

Pondération (charte ② — analyse de sensibilité à la carte) :
    --poids "logement=0.50,emploi=0.20,demographie=0.20,formation=0.10"
    (les 4 clés ou rien ; la somme doit faire 1 ; défaut = 30/25/25/20)

Mode interactif (l'utilisateur choisit tout ses chiffres au clavier) :
    python transform/simulateur.py --interactif

Sortie : tableau avant/après en console + data/processed/simulateur_scenarios.csv
(append : chaque simulation ajoute une ligne, horodatée, pour tracer l'historique).
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROCESSED = Path("data/processed/villes_scoring.csv")
OUT = Path("data/processed/simulateur_scenarios.csv")

# ---------------------------------------------------------------------------
# Poids et formules — IDENTIQUES à transform/scores.py (source de vérité).
# Si tu changes les poids dans scores.py, change-les ici aussi.
# ---------------------------------------------------------------------------
W = {"logement": 0.30, "emploi": 0.25, "demographie": 0.25, "formation": 0.20}

# Colonnes attendues : liste de noms candidats (le premier trouvé gagne).
COLS = {
    "ville": ["ville", "Ville", "nom_ville"],
    "prix": ["prix_m2_median_appart", "prix_m2"],
    "pop": ["pop", "population", "pop_totale"],
    "chomage": ["taux_chomage"],
    "effort": ["taux_effort_logement", "taux_effort"],
    "cadres": ["part_cadres"],
    "prof_interm": ["part_prof_interm", "part_prof_intermediaire"],
    "densite": ["densite_etudiante"],
    "part_15_24": ["part_15_24", "part_15_24_ans"],
    "dipl_sup": ["part_dipl_sup", "part_diplomes_sup"],
    "etudiants": ["effectifs", "effectif_etudiants", "etudiants"],
    "score": ["score_global", "score"],
    "rang": ["rang"],
}

# Heuristique effort (identique à scores.py) : loyer mensuel d'un studio 20 m²
# ≈ 0,5 % de la valeur d'achat par mois ; budget étudiant 800 €/mois.
# => taux_effort (%) = 100 * (0.005 * prix * 20) / 800 = prix / 80
BUDGET_ETUDIANT = 800.0
SURFACE_STUDIO = 20.0
TAUX_LOYER_VALEUR = 0.005


def effort_depuis_prix(prix: float) -> float:
    """Taux d'effort (%) d'un studio 20 m², budget 800 €/mois."""
    loyer = TAUX_LOYER_VALEUR * prix * SURFACE_STUDIO
    return 100.0 * loyer / BUDGET_ETUDIANT


def resoudre_colonnes(df: pd.DataFrame) -> dict:
    """Mappe chaque clé logique vers la vraie colonne du CSV."""
    found, manquantes = {}, []
    for cle, candidats in COLS.items():
        match = next((c for c in candidats if c in df.columns), None)
        if match is None:
            manquantes.append(cle)
        else:
            found[cle] = match
    if manquantes:
        print("Colonnes disponibles dans villes_scoring.csv :")
        print(list(df.columns))
        print(f"Clés sans colonne trouvée : {manquantes}")
        print("-> coller la sortie --inspect dans le chat pour adapter COLS.")
        sys.exit(1)
    return found


def minmax(serie: pd.Series, inverser: bool = False) -> pd.Series:
    """Normalisation min-max 0-100, éventuellement inversée (bas = meilleur)."""
    lo, hi = serie.min(), serie.max()
    if hi == lo:
        return pd.Series(50.0, index=serie.index)
    s = 100.0 * (serie - lo) / (hi - lo)
    return 100.0 - s if inverser else s


def recompute(df: pd.DataFrame, cols: dict, w: dict | None = None) -> pd.DataFrame:
    """Recalcule piliers + score global + rang à partir des indicateurs."""
    poids = w if w is not None else W
    n_prix = minmax(df[cols["prix"]], inverser=True)
    n_effort = minmax(df[cols["effort"]], inverser=True)
    n_chom = minmax(df[cols["chomage"]], inverser=True)
    n_cadres = minmax(df[cols["cadres"]])
    n_pi = minmax(df[cols["prof_interm"]])
    n_dens = minmax(df[cols["densite"]])
    n_1524 = minmax(df[cols["part_15_24"]])
    n_dipl = minmax(df[cols["dipl_sup"]])
    n_etu = minmax(df[cols["etudiants"]])

    out = df.copy()
    out["pilier_logement"] = (0.7 * n_prix + 0.3 * n_effort).round(1)
    out["pilier_emploi"] = (0.5 * n_chom + 0.3 * n_cadres + 0.2 * n_pi).round(1)
    out["pilier_demographie"] = (0.6 * n_dens + 0.4 * n_1524).round(1)
    out["pilier_formation"] = (0.7 * n_etu + 0.3 * n_dipl).round(1)
    out["score_global_calc"] = (
        poids["logement"] * out["pilier_logement"]
        + poids["emploi"] * out["pilier_emploi"]
        + poids["demographie"] * out["pilier_demographie"]
        + poids["formation"] * out["pilier_formation"]
    ).round(1)
    out["rang_calc"] = out["score_global_calc"].rank(ascending=False, method="min").astype(int)
    return out


def parse_delta(s: str) -> float:
    """'+10' -> +10, '-10' -> -10, '5' -> +5."""
    s = s.strip()
    if s.startswith(("+", "-")):
        return float(s)
    return float(s) if float(s) < 0 else float(s)


def appliquer(df: pd.DataFrame, cols: dict, ville: str, opts) -> pd.DataFrame:
    """Applique le scénario what-if et retourne le DataFrame modifié."""
    df = df.copy()

    if opts.prix is not None:
        m = df[cols["ville"]] == ville
        df.loc[m, cols["prix"]] = df.loc[m, cols["prix"]] * (1 + parse_delta(opts.prix) / 100.0)
        # Le taux d'effort est mécaniquement dérivé du prix -> recalcul
        df.loc[m, cols["effort"]] = df.loc[m, cols["prix"]].map(effort_depuis_prix)
        print(f"  Prix m² {ville} : {parse_delta(opts.prix):+.0f} %  (et taux d'effort recalculé)")

    if opts.chomage is not None:
        m = df[cols["ville"]] == ville
        avant = df.loc[m, cols["chomage"]]
        df.loc[m, cols["chomage"]] = (avant + parse_delta(opts.chomage)).clip(lower=0)
        print(f"  Chômage {ville} : {parse_delta(opts.chomage):+.1f} point(s)")

    if opts.etudiants is not None:
        m = df[cols["ville"]] == ville
        df.loc[m, cols["etudiants"]] = df.loc[m, cols["etudiants"]] + parse_delta(opts.etudiants)
        # La densité étudiante est dérivée des effectifs -> recalcul si pop dispo
        if "pop" in cols:
            df.loc[m, cols["densite"]] = (
                100.0 * df.loc[m, cols["etudiants"]] / df.loc[m, cols["pop"]]
            )
            print(f"  Effectifs étudiants {ville} : {parse_delta(opts.etudiants):+.0f} (densité recalculée)")
        else:
            print(f"  Effectifs étudiants {ville} : {parse_delta(opts.etudiants):+.0f}")

    if opts.part_cadres is not None:
        m = df[cols["ville"]] == ville
        df.loc[m, cols["cadres"]] = (
            df.loc[m, cols["cadres"]] + parse_delta(opts.part_cadres)
        ).clip(0, 100)
        print(f"  Part de cadres {ville} : {parse_delta(opts.part_cadres):+.1f} point(s)")

    if opts.part_15_24 is not None:
        m = df[cols["ville"]] == ville
        df.loc[m, cols["part_15_24"]] = (
            df.loc[m, cols["part_15_24"]] + parse_delta(opts.part_15_24)
        ).clip(0, 100)
        print(f"  Part 15-24 ans {ville} : {parse_delta(opts.part_15_24):+.1f} point(s)")

    if opts.part_dipl_sup is not None:
        m = df[cols["ville"]] == ville
        df.loc[m, cols["dipl_sup"]] = (
            df.loc[m, cols["dipl_sup"]] + parse_delta(opts.part_dipl_sup)
        ).clip(0, 100)
        print(f"  Part diplômés sup {ville} : {parse_delta(opts.part_dipl_sup):+.1f} point(s)")

    return df


def afficher_comparatif(avant: pd.DataFrame, apres: pd.DataFrame, cols: dict, ville: str):
    """Tableau avant/après pour la ville ciblée + top 10 recalculé."""
    a = avant[avant[cols["ville"]] == ville].iloc[0]
    b = apres[apres[cols["ville"]] == ville].iloc[0]

    print(f"\n{'=' * 70}")
    print(f"  WHAT-IF — {ville}")
    print(f"{'=' * 70}")
    lignes = [
        ("Score global", a["score_global_calc"], b["score_global_calc"]),
        ("Rang", a["rang_calc"], b["rang_calc"]),
        ("Pilier logement", a["pilier_logement"], b["pilier_logement"]),
        ("Pilier emploi", a["pilier_emploi"], b["pilier_emploi"]),
        ("Pilier démographie", a["pilier_demographie"], b["pilier_demographie"]),
        ("Pilier formation", a["pilier_formation"], b["pilier_formation"]),
    ]
    print(f"  {'Indicateur':<22}{'Avant':>10}{'Après':>10}{'Δ':>12}")
    for nom, va, vb in lignes:
        if nom == "Rang":
            d = int(vb - va)
            fleche = " ↑" if d < 0 else (" ↓" if d > 0 else "")
            print(f"  {nom:<22}{int(va):>10}{int(vb):>10}{d:>+12d}{fleche}")
        else:
            d = vb - va
            fleche = "  <-" if d != 0 else ""
            print(f"  {nom:<22}{va:>10}{vb:>10}{d:>+10.1f}{fleche}")

    print(f"\n  Top 10 après simulation :")
    top = apres.sort_values("score_global_calc", ascending=False).head(10)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        marque = "  <-- " + ville if r[cols["ville"]] == ville else ""
        print(f"   {i:>2}. {r[cols['ville']]:<18}{r['score_global_calc']:>6}{marque}")

    print(
        "\n  ⚠️ Lecture : variation de score à MÉTHODOLOGIE CONSTANTE. "
        "Ceci n'affirme aucun lien causal entre la politique simulée "
        "et l'indicateur modifié."
    )


def sauvegarder(avant, apres, cols, ville, opts):
    """Append la simulation dans data/processed/simulateur_scenarios.csv."""
    a = avant[avant[cols["ville"]] == ville].iloc[0]
    b = apres[apres[cols["ville"]] == ville].iloc[0]
    record = {
        "horodatage": datetime.now().isoformat(timespec="seconds"),
        "ville": ville,
        "scenario": ", ".join(
            f"{k[2:].replace('_', ' ')}={v}" for k, v in vars(opts).items()
            if v is not None and k not in ("ville", "inspect", "interactif", "poids")
        ) or "re-classement (aucun indicateur modifié)",
        "score_avant": a["score_global_calc"],
        "score_apres": b["score_global_calc"],
        "rang_avant": int(a["rang_calc"]),
        "rang_apres": int(b["rang_calc"]),
    }
    df_rec = pd.DataFrame([record])
    if OUT.exists():
        df_rec.to_csv(OUT, mode="a", header=False, index=False)
    else:
        df_rec.to_csv(OUT, index=False)
    print(f"\n  Simulation ajoutée à {OUT}")


def verifier_plausibilite(avant: pd.DataFrame, apres: pd.DataFrame, cols: dict, ville: str):
    """Avertit (sans bloquer) si la simulation produit des valeurs peu plausibles.
    Règles heuristiques volontairement simples — un scénario extrême reste
    possible, mais il doit être assumé comme exercice théorique."""
    if ville == "TOUTES" or ville not in set(apres[cols["ville"]]):
        return  # scénario panel entier : pas de vérification ville par ville
    a = avant[avant[cols["ville"]] == ville].iloc[0]
    b = apres[apres[cols["ville"]] == ville].iloc[0]
    alertes = []

    dp = (b[cols["prix"]] - a[cols["prix"]]) / a[cols["prix"]] * 100.0
    if abs(dp) > 30:
        alertes.append(f"prix m² {dp:+.0f} % (au-delà de ±30 %)")

    ch = b[cols["chomage"]]
    if ch < 3 or ch > 30:
        alertes.append(f"taux de chômage à {ch:.1f} % (hors plage plausible 3-30 %)")

    if b[cols["densite"]] > 60:
        alertes.append(f"densité étudiante à {b[cols['densite']]:.0f} % (>60 %)")

    de = (b[cols["etudiants"]] - a[cols["etudiants"]]) / a[cols["etudiants"]]
    if abs(de) > 0.5:
        alertes.append(f"effectifs étudiants {de:+.0%} (au-delà de ±50 %)")

    if b[cols["part_15_24"]] > 40:
        alertes.append(f"part 15-24 ans à {b[cols['part_15_24']]:.1f} % (>40 %)")

    if b[cols["dipl_sup"]] > 80:
        alertes.append(f"part diplômés sup à {b[cols['dipl_sup']]:.1f} % (>80 %)")

    if alertes:
        print("\n  ⚠️ VALEURS PEU PLAUSIBLES (scénario extrême assumé comme exercice théorique) :")
        for al in alertes:
            print(f"     - {al}")


def parse_poids(s: str) -> dict:
    """'logement=0.5,emploi=0.2,...' -> dict validé (somme = 1)."""
    w = {}
    for part in s.split(","):
        cle, _, val = part.strip().partition("=")
        cle = cle.strip().lower()
        if cle not in W:
            sys.exit(f"Clé de poids inconnue '{cle}'. Clés valides : {', '.join(W)}")
        try:
            w[cle] = float(val)
        except ValueError:
            sys.exit(f"Valeur de poids invalide : '{val}' pour {cle}")
    if set(w) != set(W):
        sys.exit(f"Il faut les 4 poids. Manquants : {sorted(set(W) - set(w))}")
    if abs(sum(w.values()) - 1.0) > 1e-6:
        sys.exit(f"La somme des poids doit faire 1 (actuellement {sum(w.values()):.2f})")
    return w


def mode_interactif(df, cols) -> None:
    """L'utilisateur choisit ville, chiffres et poids au clavier, pas à pas."""
    villes = list(df[cols["ville"]])
    print("\n" + "=" * 70)
    print("  SIMULATEUR INTERACTIF — Atlas de l'attractivité étudiante")
    print("=" * 70)
    print("\nVilles du panel :")
    for i, v in enumerate(villes, 1):
        print(f"  {i:>2}. {v}")

    # Choix de la ville
    while True:
        choix = input("\nNuméro ou nom de la ville ciblée : ").strip()
        if choix.isdigit() and 1 <= int(choix) <= len(villes):
            ville = villes[int(choix) - 1]
            break
        if choix in villes:
            ville = choix
            break
        print("  Choix invalide, réessaie (numéro de la liste ou nom exact).")

    ligne = df[df[cols["ville"]] == ville].iloc[0]
    print(f"\nValeurs actuelles de {ville} :")
    print(f"  Prix m² médian       : {ligne[cols['prix']]:>10.1f} €")
    print(f"  Taux de chômage      : {ligne[cols['chomage']]:>10.1f} %")
    print(f"  Effectifs étudiants  : {ligne[cols['etudiants']]:>10.0f}")
    print(f"  Part de cadres       : {ligne[cols['cadres']]:>10.1f} %")
    print(f"  Part 15-24 ans       : {ligne[cols['part_15_24']]:>10.1f} %")
    print(f"  Part diplômés sup    : {ligne[cols['dipl_sup']]:>10.1f} %")

    class Opts:
        pass
    opts = Opts()
    opts.ville = ville

    def demande(label, cle):
        while True:
            raw = input(f"{label} (Entrée = ne pas changer) : ").strip().replace(",", ".")
            if raw == "":
                setattr(opts, cle, None)
                return
            try:
                val = float(raw)
                setattr(opts, cle, f"{val:+}")
                return
            except ValueError:
                print("  Nombre attendu (ex: -10 ou +2.5), réessaie.")

    print("\nEntre tes chiffres — signe obligatoire (+ ou -), Entrée pour sauter :")
    demande("Prix m² en % (ex: -10)", "prix")
    demande("Chômage en points (ex: -2)", "chomage")
    demande("Effectifs étudiants (ex: +5000)", "etudiants")
    demande("Part de cadres en points (ex: +5)", "part_cadres")
    demande("Part 15-24 ans en points (ex: +2)", "part_15_24")
    demande("Part diplômés sup en points (ex: +5)", "part_dipl_sup")

    if all(getattr(opts, c) is None for c in
           ("prix", "chomage", "etudiants", "part_cadres", "part_15_24", "part_dipl_sup")):
        print("\nAucun changement demandé — simulation neutre (re-classement uniquement).")

    # Poids : défaut ou personnalisés
    poids = None
    raw = input(
        "\nPoids des piliers personnalisés ? (Entrée = défaut 30/25/25/20, "
        "sinon format logement=0.5,emploi=0.2,demographie=0.2,formation=0.1) : "
    ).strip()
    if raw:
        poids = parse_poids(raw)
        print(f"  Poids utilisés : {poids}")

    avant = recompute(df, cols, poids)
    apres = recompute(appliquer(df, cols, ville, opts), cols, poids)

    verifier_plausibilite(df, apres, cols, ville)

    if poids is None:
        ecart = (avant["score_global_calc"] - df[cols["score"]]).abs().max()
        print(f"\nCohérence (poids par défaut) : écart max CSV vs recalcul = {ecart:.2f} pts")

    afficher_comparatif(avant, apres, cols, ville)
    sauvegarder(avant, apres, cols, ville, opts)

    again = input("\nAutre simulation ? (o/N) : ").strip().lower()
    if again == "o":
        mode_interactif(df, cols)


def main():
    p = argparse.ArgumentParser(description="Simulateur What-if — Atlas attractivité étudiante")
    p.add_argument("--inspect", action="store_true", help="Affiche les colonnes du CSV et 3 lignes")
    p.add_argument("--ville", required=False, help="Ville ciblée, ou TOUTES")
    p.add_argument("--prix", help="Variation du prix m² en % (ex: -10)")
    p.add_argument("--chomage", help="Variation du taux de chômage en points (ex: -2)")
    p.add_argument("--etudiants", help="Variation absolue des effectifs (ex: +5000)")
    p.add_argument("--part-cadres", dest="part_cadres", help="Variation en points (ex: +5)")
    p.add_argument("--part-15-24", dest="part_15_24", help="Variation en points (ex: +2)")
    p.add_argument("--part-dipl-sup", dest="part_dipl_sup", help="Variation en points (ex: +5)")
    p.add_argument(
        "--poids",
        help='Poids des piliers (ex: "logement=0.5,emploi=0.2,demographie=0.2,formation=0.1")',
    )
    p.add_argument(
        "--interactif", action="store_true", help="Mode interactif : tout au clavier"
    )
    opts = p.parse_args()

    if not PROCESSED.exists():
        sys.exit(f"ERREUR : {PROCESSED} introuvable. Lancer d'abord transform/scores.py.")

    df = pd.read_csv(PROCESSED)
    cols = resoudre_colonnes(df)

    if opts.interactif:
        mode_interactif(df, cols)
        return

    if opts.inspect:
        print(f"Colonnes de {PROCESSED} :")
        for c in df.columns:
            print(f"  - {c}  ({df[c].dtype})")
        print("\n3 premières lignes :")
        print(df.head(3).to_string())
        print("\nVilles du panel :", ", ".join(df[cols["ville"]]))
        return

    if opts.ville is None:
        sys.exit("Donne --ville (ou --ville TOUTES) ou --inspect.")

    villes = list(df[cols["ville"]])
    if opts.ville != "TOUTES" and opts.ville not in villes:
        sys.exit(f"Ville inconnue '{opts.ville}'. Villes : {', '.join(villes)}")

    cible = villes if opts.ville == "TOUTES" else [opts.ville]

    poids = parse_poids(opts.poids) if opts.poids else None
    if poids:
        print(f"\nPoids personnalisés : {poids}")

    avant = recompute(df, cols, poids)
    apres = recompute(appliquer(df, cols, opts.ville, opts), cols, poids)

    verifier_plausibilite(df, apres, cols, opts.ville)

    if poids is None:
        print(f"\nVérification de cohérence (scores du CSV vs recalcul, sans scénario) :")
        ecart = (avant["score_global_calc"] - df[cols["score"]]).abs().max()
        print(f"  Écart max score CSV vs recalcul : {ecart:.2f} pts (doit être proche de 0)")
        if ecart > 1.0:
            print("  ⚠️ Écart élevé : les formules ici divergent de scores.py -> coller ce message dans le chat.")

    for v in cible:
        afficher_comparatif(avant, apres, cols, v)
        sauvegarder(avant, apres, cols, v, opts)


if __name__ == "__main__":
    main()