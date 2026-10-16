"""
Analyse de sensibilité des pondérations (charte qualité ②)
===========================================================
Vérifie la robustesse du classement : rejoue le score global avec plusieurs
scénarios de poids piliers et montre si le top 5 bouge.

Usage :
    python transform/sensibilite.py

Entrée : data/processed/villes_scoring.csv (déjà calculé par transform/scores.py)
Sortie  : tableau console (à coller dans le chat) + graphique PNG
          data/processed/sensibilite_top5.png (si matplotlib dispo)

Scénarios :
    actuel        : 30/25/25/20 (référence = scores.py)
    egalitaire    : 25/25/25/25
    pro_logement  : 50/20/15/15
    pro_emploi    : 20/50/15/15
    pro_demo      : 20/15/50/15
    pro_formation : 20/15/15/50
"""

import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
PROCESSED = RACINE / "data" / "processed"

SCENARIOS = {
    #            logement, emploi, démo, formation
    "actuel":        (0.30, 0.25, 0.25, 0.20),
    "egalitaire":    (0.25, 0.25, 0.25, 0.25),
    "pro_logement":  (0.50, 0.20, 0.15, 0.15),
    "pro_emploi":    (0.20, 0.50, 0.15, 0.15),
    "pro_demo":      (0.20, 0.15, 0.50, 0.15),
    "pro_formation": (0.20, 0.15, 0.15, 0.50),
}


def main() -> None:
    chemin = PROCESSED / "villes_scoring.csv"
    if not chemin.exists():
        sys.exit("[ERREUR] Lancer d'abord `python transform/scores.py` "
                 f"(introuvable : {chemin})")
    df = pd.read_csv(chemin)

    # --- 1. Classement par scénario -------------------------------------------
    resultats = {}
    for nom, (wl, we, wd, wf) in SCENARIOS.items():
        s = (wl * df["score_logement"] + we * df["score_emploi"]
             + wd * df["score_demographie"] + wf * df["score_formation"])
        classement = df["ville"].loc[s.sort_values(ascending=False).index].tolist()
        resultats[nom] = classement

    # --- 2. Tableau : top 5 par scénario ---------------------------------------
    print("=" * 78)
    print("TOP 5 PAR SCÉNARIO DE PONDÉRATION")
    print("=" * 78)
    lignes = []
    for nom, cl in resultats.items():
        lignes.append([nom] + cl[:5])
    print(pd.DataFrame(lignes, columns=["scénario", "1", "2", "3", "4", "5"])
          .to_string(index=False))

    # --- 3. Robustesse : présence dans le top 5 / rang moyen -------------------
    from collections import defaultdict
    tops = defaultdict(list)
    for nom, cl in resultats.items():
        for i, v in enumerate(cl[:5]):
            tops[v].append(i + 1)
    robustesse = pd.DataFrame(
        [{"ville": v, "nb_top5": len(r), "rang_moyen": sum(r) / len(r)}
         for v, r in tops.items()]
    ).sort_values(["nb_top5", "rang_moyen"], ascending=[False, True])
    print(f"\nROBUSTESSE (sur {len(SCENARIOS)} scénarios)")
    print(robustesse.to_string(index=False))

    # --- 4. Graphique : rang du top 5 actuel selon le scénario -----------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        top5_actuel = resultats["actuel"][:5]
        fig, ax = plt.subplots(figsize=(10, 5))
        for v in top5_actuel:
            rangs = [resultats[n].index(v) + 1 for n in SCENARIOS]
            ax.plot(list(SCENARIOS), rangs, marker="o", label=v)
        ax.invert_yaxis()
        ax.set_ylabel("Rang")
        ax.set_title("Robustesse du top 5 selon la pondération des piliers")
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        fig_path = PROCESSED / "sensibilite_top5.png"
        fig.savefig(fig_path, dpi=150)
        print(f"\nGraphique : {fig_path}")
    except ImportError:
        print("\n[INFO] matplotlib absent — graphique sauté "
              "(pip install matplotlib pour l'obtenir).")

    print("\n>>> Coller TOUTE cette sortie dans le chat pour analyse.")


if __name__ == "__main__":
    main()