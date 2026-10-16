"""
Régression — élasticité prix ↔ attractivité (KPI 4, charte ⑨)
==============================================================
Estime l'élasticité du prix du m² par rapport à l'attractivité étudiante
(densité étudiante = proxy d'attractivité), avec INTERVALLES DE CONFIANCE
bootstrap (honnêteté = réflexe attendu par un jury d'économistes).

⚠️ n = 20 : résultats EXPLICATIFS/exploratoires, pas causaux. Corrélation ≠
causalité (le prix monte AUSSI parce que les villes attractives sont chères).

Usage :
    python transform/regression.py           # régression + bootstrap + graphique
    python transform/regression.py --simple  # sans graphique

Entrée : data/processed/villes_scoring.csv
Sorties : console (à coller dans le chat)
          data/processed/regression_elasticite.png
          data/processed/regression_coef.csv (pour le site React/simulateur)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
PROCESSED = RACINE / "data" / "processed"

N_BOOT = 2000
SEED = 42


def ols_loglog(df: pd.DataFrame) -> dict:
    """ln(prix_m2) ~ ln(densite_etudiante) + taux_chomage, via numpy (sans biais sklearn)."""
    d = df.dropna(subset=["prix_m2", "densite_etudiante", "taux_chomage"]).copy()
    # Strasbourg prix imputé → exclu de la régression (honnêteté)
    n_avant = len(d)
    d = d[~d["ville"].str.contains("trasbourg", case=False, na=False)]
    if n_avant - len(d):
        print(f"[INFO] Strasbourg exclu de la régression (prix imputé). n = {len(d)}.")

    X = np.column_stack([
        np.ones(len(d)),
        np.log(d["densite_etudiante"].values),
        d["taux_chomage"].values,
    ])
    y = np.log(d["prix_m2"].values)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ beta
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    return {"df": d, "beta": beta, "r2": r2}


def bootstrap_ci(df: pd.DataFrame) -> dict:
    """IC 95 % bootstrap par rééchantillonnage des résidus... non : des individus."""
    rng = np.random.default_rng(SEED)
    betas = []
    d = df.reset_index(drop=True)
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(d), size=len(d))
        ech = d.iloc[idx]
        try:
            res = ols_loglog(ech)
            betas.append(res["beta"])
        except Exception:
            continue
    betas = np.array(betas)
    ci = np.percentile(betas, [2.5, 97.5], axis=0)
    return {"coef": betas.mean(axis=0), "ci_bas": ci[0], "ci_haut": ci[1]}


def main() -> None:
    chemin = PROCESSED / "villes_scoring.csv"
    if not chemin.exists():
        sys.exit(f"[ERREUR] Lancer d'abord transform/scores.py (introuvable : {chemin})")
    df = pd.read_csv(chemin)

    print("Modèle : ln(prix_m2) = a + b·ln(densité_étudiante) + c·taux_chomage")
    print(f"Bootstrap : {N_BOOT} rééchantillonnages (IC 95 %)\n")
    res = ols_loglog(df)
    a, b, c = res["beta"]
    print(f"R² = {res['r2']:.3f}   n = {len(res['df'])} villes (hors Strasbourg)")

    boot = bootstrap_ci(res["df"])
    labels = ["constante", "b (élasticité densité étudiante)", "c (effet chômage)"]
    for i, lab in enumerate(labels):
        print(f"  {lab:38s} {boot['coef'][i]:+.4f}   "
              f"IC95 % [{boot['ci_bas'][i]:+.4f} ; {boot['ci_haut'][i]:+.4f}]")

    # --- Simulateur : effet d'une baisse de prix sur la densité (inverse du modèle) ---
    print("\n--- Simulateur (illustratif, corrélation ≠ causalité) ---")
    print(f"Élasticité b = {b:+.3f} : +10 % de densité étudiante ↔ "
          f"{100 * (np.exp(b) - 1):+.1f} % de prix m²")
    b_inv = 1 / b
    print(f"Lecture inverse : un marché 10 % moins cher est associé à "
          f"{100 * (1.1 ** b_inv - 1):+.1f} % de densité étudiante")

    # --- Export des coefficients pour le site ---
    coef_df = pd.DataFrame({
        "parametre": ["constante", "elasticite_densite", "effet_chomage", "r2", "n"],
        "valeur": [a, b, c, res["r2"], len(res["df"])],
        "ic95_bas": [boot["ci_bas"][0], boot["ci_bas"][1], boot["ci_bas"][2], None, None],
        "ic95_haut": [boot["ci_haut"][0], boot["ci_haut"][1], boot["ci_haut"][2], None, None],
    })
    coef_path = PROCESSED / "regression_coef.csv"
    coef_df.to_csv(coef_path, index=False)
    print(f"\nCoefficients exportés : {coef_path}")

    # --- Graphique nuage + droite ---
    if "--simple" in sys.argv:
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        d = res["df"]
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(d["densite_etudiante"], d["prix_m2"], s=60, alpha=0.8)
        for _, r in d.iterrows():
            ax.annotate(r["ville"], (r["densite_etudiante"], r["prix_m2"]),
                        fontsize=8, alpha=0.7,
                        xytext=(4, 4), textcoords="offset points")
        xs = np.linspace(d["densite_etudiante"].min(), d["densite_etudiante"].max(), 100)
        ys = np.exp(a + b * np.log(xs) + c * d["taux_chomage"].mean())
        ax.plot(xs, ys, "r--", label=f"ajustement log-log (R²={res['r2']:.2f})")
        ax.set_xlabel("Densité étudiante (étudiants / population, %)")
        ax.set_ylabel("Prix m² médian (€)")
        ax.set_title("Prix du m² vs attractivité étudiante — 19 villes (hors Strasbourg)")
        ax.legend()
        ax.grid(alpha=0.3)
        plt.tight_layout()
        fig_path = PROCESSED / "regression_elasticite.png"
        plt.savefig(fig_path, dpi=150)
        print(f"Graphique : {fig_path}")
    except ImportError:
        print("[INFO] matplotlib absent — graphique sauté.")

    print("\n>>> Coller TOUTE cette sortie dans le chat pour interprétation.")


if __name__ == "__main__":
    main()