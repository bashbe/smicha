# Instructions Claude Code — smiha-flask

## OBLIGATOIRE : lire README.md avant tout

Avant toute analyse, modification ou génération de code/JSON dans ce projet,
tu DOIS lire `README.md` en entier. Il contient :

- Le format officiel des questions (source de vérité pour l'import JSON)
- Les valeurs autorisées (`VALID_SECTIONS`, `VALID_PARCOURS`)
- Les règles de maintenance à respecter impérativement
- L'architecture, la logique métier et les invariantes critiques

Ne pas lire `README.md` avant de répondre = risque de générer du JSON invalide
ou de casser une invariante métier (filtrage des sections, format des questions, etc.).

## Règles de maintenance (rappel)

- Toute modification de `question_types.py` → mettre à jour README + `sample_questions.json`
- Toute modification du code → vérifier manuellement les interfaces impactées
  (`/app/home`, `/app/parcours`, `/app/chapitre/…`, `/app/revision`, `/admin/*`, `/auth`)
- L'interface est en hébreu RTL — toujours tester l'alignement après modification HTML/CSS
