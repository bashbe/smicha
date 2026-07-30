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

## Parcours multi-chelek — `chupa_kidushin` (חופה וקידושין)

Ce parcours (ajouté le 2026-07-30 dans `question_types.py` : `VALID_PARCOURS`,
`PARCOURS_LABELS`, `PARCOURS_DESCRIPTIONS`, + `static/js/chapitre.js` et
`static/js/admin-question-editor.js`) a une particularité que n'a **aucun autre
parcours de l'app** : il va couvrir, au fil des imports, des simanim provenant
de **deux chalakim différents** du Choulhan Aroukh — **אבן העזר** (hilkhot
kidoushin/ichout) ET **חושן משפט** (aspects monétaires liés au mariage :
ketouba, tenaim, etc.). Ce n'est PAS un cas comme `bassar_bechalav`, qui reste
entièrement dans un seul chelek (Yoré Dé'a).

**Problème structurel non résolu** : le modèle de données (`models.py`,
`Question.siman`) est un simple `Integer`, sans aucune notion de « chelek ».
`Subject` est unique par `(parcours, siman, title)`, la révision par siman
(`/app/revision/siman`), et le regroupement des cartes dans `/app/parcours`
raisonnent tous sur `(parcours, siman)` seul. Si un siman d'Even haEzer et un
siman de Choshen Mishpat portent un jour le **même numéro** dans ce parcours,
ils se mélangeront silencieusement (mêmes sujets, même liste de révision par
siman, etc.) — c'est un vrai risque de collision, pas une simple question de
présentation.

**Solution provisoire actuellement en place** (le temps de générer du contenu
sans bloquer) : chaque question du parcours `chupa_kidushin` porte un préfixe
de chelek dans le champ optionnel `source` du JSON d'import (voir
`prompt_generation_questions.md` — champ libre sérialisé tel quel dans
`Question.source_ref` par `_source_to_ref()`) :
```json
"source": { "chelek": "ehy", "siman": 26, "seif": 1, "posek": "מחבר" }
```
- `chelek: "ehy"` = אבן העזר
- `chelek: "chum"` = חושן משפט

Les fichiers de lot générés suivent la même convention de nommage, sous
`docs/generated_questions/` (fichiers de travail, non liés au code de l'app — voir
« Organisation des fichiers non liés à l'app » ci-dessous) :
`generated_questions_ehy_<siman>.json` / `generated_questions_chum_<siman>.json`,
de même que tout dossier de textes sources Sefaria sauvegardés pour validation
(`ehy_<siman>.*` / `chum_<siman>.*`). Ce préfixe est un **pense-bête textuel**,
il n'empêche aucune collision réelle côté base de données.

`scripts/fetch_sefaria_text.py` (stdlib uniquement) récupère un siman depuis l'API Sefaria et
l'enregistre dans `docs/sefaria_sources/` avec cette même convention — à lancer depuis un
environnement ayant un accès réseau non restreint (l'API Sefaria est bloquée dans les sessions
Claude Code de ce projet, voir `docs/journal_chupa_kidushin.md`).

**Il récupère toutes les couches que l'examen couvre, pas seulement le Choulhan Aroukh** — sinon
une carte taguée `tur` ou `ptei_teshuva` reste invérifiable :

| exam_section | couches récupérées |
|---|---|
| `shulchan_aruch` | Choulhan Aroukh, חלקת מחוקק, בית שמואל |
| `tur` | טור, בית יוסף, דרכי משה |
| `ptei_teshuva` | פתחי תשובה |

Volontairement limité à ces textes principaux (demande explicite de l'utilisateur,
2026-07-30) : Sefaria lie des dizaines d'autres œuvres à chaque siman (ביאור הגר"א,
Be'er HaGolah, Ba'er Hetev, ט"ז, ועוד) — non téléchargées, elles ressortent en
« non suivi » dans `--discover`.

Les œuvres autonomes (SA, Tour, Beit Yossef, Darkei Moshe) sont récupérées par titre
(`DIRECT_WORKS` dans le script) ; les commentaires sont **découverts via l'API `links`** de
Sefaria plutôt que codés en dur, leurs titres exacts n'ayant pas pu être vérifiés depuis une
session Claude Code. Lancer `--discover` sur un siman liste ce que Sefaria expose réellement
(sans rien écrire) : c'est le point de départ si un titre de `DIRECT_WORKS` renvoie un 404.
Sortie par siman : un fichier par couche (`ehy_26_beit_shmuel.txt`…) plus un
`ehy_26_ALL.txt` groupé par section d'examen — c'est ce dernier qu'il faut donner à un agent
de vérification.

### 🔧 Prompt pour un futur agent — à faire dès que possible

> Le parcours `chupa_kidushin` mélange aujourd'hui des simanim d'Even haEzer
> et de 'Hochen Mishpat sans distinction structurelle — seul le texte libre
> `source_ref` (préfixe `ehy`/`chum`) les différencie, ce qui ne protège pas
> contre une collision de numéros de siman entre les deux chalakim. Avant
> d'importer du contenu 'Hochen Mishpat (`chum`) dans ce parcours, ou si un
> siman `chum` risque de porter le même numéro qu'un siman `ehy` déjà importé :
> 1. Vérifie s'il y a déjà collision réelle (`Question.query.filter_by(parcours="chupa_kidushin")`
>    groupé par `siman`, en croisant avec le préfixe de `source_ref`).
> 2. Propose et implémente une vraie séparation structurelle — la plus probable :
>    ajouter une colonne `chelek` (ou `chelek_prefix`) à `Question` et `Subject`,
>    l'inclure dans la contrainte d'unicité de `Subject` (`parcours, chelek, siman, title`),
>    et l'utiliser partout où le code groupe par `(parcours, siman)` seul
>    (`/app/parcours`, `/app/revision/siman`, `subjects.get_or_create_subject`,
>    l'import admin, etc.) — avec une migration pour les données existantes.
> 3. Mets à jour ce README et ce CLAUDE.md une fois la vraie colonne en place,
>    et retire la convention `ehy`/`chum` dans `source_ref` (ou garde-la en plus,
>    à titre d'affichage humain, une fois qu'elle n'est plus le seul filet de
>    sécurité).
> Ne fais PAS cette migration structurelle toi-même sans lire d'abord tout
> l'historique des imports `chupa_kidushin` (journal de génération dans
> `docs/journal_chupa_kidushin.md` s'il existe encore) pour connaître l'état
> réel des données avant de migrer.

## Organisation des fichiers non liés à l'app (contenu, pas code)

Pour garder la racine du repo lisible, tout ce qui est **contenu de génération de cartes**
(pas du code d'app, pas de la config) vit sous `docs/` :

| Dossier | Contenu |
|---|---|
| `docs/generated_questions/` | Lots JSON produits par `/generate-cards` (`generated_questions_<parcours>_<siman>.json`) — fichiers de travail, gitignorés par défaut (voir `.gitignore`), commités seulement pour la continuité d'une session ou sur demande explicite |
| `docs/source_texts/` | Textes source complets sauvegardés pour reproductibilité/vérification (extraits de séfarim fournis par l'utilisateur, ex. שו"ת היכל שלמה, טור ושו"ע) |
| `docs/sefaria_sources/` | Textes récupérés depuis l'API Sefaria via `scripts/fetch_sefaria_text.py` (voir plus haut) |
| `docs/journal_*.md`, `docs/audit_*.md`, `docs/verification_*.md` | Journaux de génération et rapports d'audit/vérification, par parcours et par session |

Racine du repo réservée au code de l'app, à sa config, et aux docs de tooling qu'un chemin en
dur référence (`prompt_generation_questions.md`, `generate_cards_lessons.md`,
`sample_questions.json`, `siman_seif_topics.json` — voir README pour ce qu'ils font). Avant de
déplacer un fichier à la racine qui ressemble à du contenu généré, vérifie d'abord qu'aucun
chemin en dur (code Python, README, CLAUDE.md, `.claude/commands/*.md`) ne le référence par son
emplacement actuel — sinon corrige ces références en même temps que le déplacement.
