# Simulation — plusieurs parcours entamés

Captures d'écran (viewport mobile) illustrant l'app quand un étudiant prépare
**plusieurs parcours en parallèle**, chacun à un stade d'avancement différent.

| Fichier | Page |
|---|---|
| `01_accueil.png` | Accueil — une section par מסלול, avec les deux tuiles d'action **carrées côte à côte** (« המשך הלמידה » / « חזרה יומית ») |
| `02_profil.png` | Profil — statistiques type Anki : KPIs, bשלות הכרטיסים (états FSRS), זיכרון ופעילות, יומן פעילות (heatmap), récap par מסלול |
| `03_mon_parcours.png` | Table des matières multi-parcours |
| `04_hub_revision.png` | Hub de révision |
| `05_choix_revision_jour.png` | Sélecteur de révision du jour (compteur de cartes dues par parcours + « הכל ») |

## Régénérer

Les captures sont produites à partir d'une base de démonstration **isolée**
(`sim_multi.db`, jamais la base réelle ; les parcours supplémentaires
`תערובות` / `מליחה` sont injectés à l'exécution et n'altèrent pas le catalogue
de production) :

```bash
# 1. (re)générer la base de simulation
python -m scripts.simulate_multi_parcours build

# 2. servir l'app sur cette base
DATABASE_URL="sqlite:///$(pwd)/sim_multi.db" FLASK_PORT=5001 \
    python -m scripts.simulate_multi_parcours serve &

# 3. capturer les écrans (nécessite playwright + chromium)
BASE_URL=http://127.0.0.1:5001 python -m scripts.screenshot_sim
```

Compte de démonstration : `demo-multi@example.com` / `password123`.
