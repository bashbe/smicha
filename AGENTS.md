# Instructions Codex — smiha-flask

## Compatibilité des workflows Claude

Au début de chaque nouvelle session dans ce dépôt, avant d'entamer toute tâche :

1. Lire `README.md` en entier.
2. Rechercher les workflows Claude locaux : `CLAUDE.md`, `.claude/commands/*.md` et `.claude/skills/**/SKILL.md` s'ils existent.
3. Appliquer leurs instructions lorsqu'elles sont pertinentes pour la demande, en les adaptant aux capacités de Codex. Une commande Claude n'est pas automatiquement exécutable dans Codex : son fichier Markdown est le cahier des charges à suivre.

### Mapping local

- Demande de génération de cartes/questions à partir d'un texte hébreu (ou mention de `/generate-cards`) : lire et appliquer intégralement `.claude/commands/generate-cards.md`, en plus du présent fichier. Avant la génération, lire aussi `prompt_generation_questions.md` comme l'impose ce workflow.

Si un workflow Claude entre en conflit avec une instruction explicite de l'utilisateur ou une règle de sécurité Codex, signaler le conflit et suivre l'instruction prioritaire.

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
