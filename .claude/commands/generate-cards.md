---
description: Génère des cartes de questions (JSON importable) à partir d'un texte source hébreu, avec double vérification et validation par question_types.py
---

# /generate-cards — Génération de cartes Smiha vérifiées

Arguments reçus : `$ARGUMENTS`
(texte source hébreu collé directement, ou chemin d'un fichier le contenant ; optionnellement
précédé de métadonnées : `siman`, `seif`, `sujet(s)` imposés, nombre de questions N.)

## Étape 0 — Prérequis

1. Lis **en entier** `prompt_generation_questions.md` (racine du repo). Le « Prompt système »
   qu'il contient est TON cahier des charges : rôle, workflow en 5 passes, politique de choix
   des types, règles pédagogiques, contraintes de format et schémas JSON. Applique-le à la lettre.
2. Lis `siman_seif_topics.json` : si le siman traité y figure, réutilise **exactement** les
   libellés de sujets existants quand le thème correspond (le champ `sujet` groupe les cartes
   dans l'app — la moindre variation de chaîne crée un groupe séparé).
3. Si `$ARGUMENTS` ne contient **aucun texte source** (ni inline, ni chemin de fichier lisible) :
   demande le texte à l'utilisateur et arrête-toi là. Ne génère JAMAIS de questions de mémoire,
   sans texte source.

## Étape 1 à 5 — Workflow du prompt de référence

Déroule les 5 passes du prompt système, dans l'ordre, sans en sauter :

1. **Lire et comprendre** le texte source en entier ; inventorier chaque din, machloket,
   chiffre légal, cas limite.
2. **Générer les questions** — couverture exhaustive par défaut (chaque din distinct → au moins
   une carte), ou exactement N si l'utilisateur l'a fixé. Politique de types :
   machloket réelle entre poskim → `multiple_opinions_dropdown` ; défaut → `multiple_choice` ;
   `true_false` seulement si vraiment pertinent (minorité du lot).
3. **Repasser sur le texte source** et auditer chaque question (fidélité, pertinence, bon type).
4. **Générer puis auditer les réponses** (pas trop faciles, halakhiquement exactes, distracteurs
   homogènes, une seule interprétation possible).
5. **Relecture linguistique hébreu + schéma** (grammaire, accords, registre, zéro lettre latine).

## Étape 6 — Validation par le code du repo (obligatoire)

Écris le lot dans le scratchpad puis valide-le avec le validateur réel :

```bash
python3 - <<'EOF'
import json, sys
sys.path.insert(0, ".")
from question_types import normalize_imported_question

with open("<scratchpad>/generated_questions.json", encoding="utf-8") as f:
    batch = json.load(f)

errors = 0
for i, q in enumerate(batch, 1):
    res = normalize_imported_question(q)
    if not res["valid"]:
        errors += 1
        print(f"Question {i}: {res['issue']}")
print(f"{len(batch)} questions, {errors} erreur(s)")
EOF
```

- S'il y a la moindre erreur : corrige les questions concernées et revalide, jusqu'à
  `0 erreur(s)`. N'affiche jamais à l'utilisateur un lot qui ne passe pas.

## Étape 7 — Livraison

1. Écris le lot final validé dans `generated_questions_<siman>.json` à la racine du repo
   (fichier de travail : ne le commite pas, sauf demande explicite).
2. Envoie le fichier à l'utilisateur avec un résumé : nombre de cartes, répartition par type et
   par difficulté, sujets utilisés, et tout choix notable (par ex. pourquoi tel din est devenu
   un `true_false` ou pourquoi deux dinim voisins ont été fusionnés en carte de discrimination).
3. Rappelle que l'import se fait via `/admin/import` (prévisualisation avant confirmation).
