# סמיכה — Smiha Path (Flask + SQLAlchemy)

Application web de préparation à l'examen de **Smiha** (ordination rabbinique). Portage complet depuis l'app d'origine TanStack Start + Supabase vers **Python / Flask / SQLAlchemy**.

L'app est entièrement en hébreu (RTL), thème sombre navy/indigo/ambre.

> **Règles de maintenance** :
>
> **Format des questions** — toute modification (`question_types.py` : champs obligatoires, types autorisés, structure `payload`) doit immédiatement déclencher :
> 1. La mise à jour de ce README (sections [Format JSON des questions](#format-json-des-questions) et [Modèle de données](#modèle-de-données))
> 2. La mise à jour de `sample_questions.json` pour refléter le nouveau format
>
> **Toute modification du code** — vérifier manuellement les interfaces concernées avant de considérer la tâche terminée :
> - Parcours étudiant : `/app/home`, `/app/parcours`, `/app/chapitre/…`, `/app/revision`
> - Back-office : `/admin/dashboard`, `/admin/import`, `/admin/validate`
> - Flux d'inscription/connexion : `/auth`, onboarding
> - RTL/hébreu : s'assurer que l'alignement et la numérotation hébraïque restent corrects
>
> Ne pas déclarer une modification terminée sans avoir navigué dans les pages impactées.

---

## Table des matières

1. [Contexte métier](#contexte-métier)
2. [Stack technique](#stack-technique)
3. [Installation rapide](#installation-rapide)
4. [Configuration](#configuration)
5. [Structure du projet](#structure-du-projet)
6. [Modèle de données](#modèle-de-données)
7. [Format JSON des questions](#format-json-des-questions)
8. [Routes et API](#routes-et-api)
9. [Logique métier clé](#logique-métier-clé)
10. [Pipeline d'import des questions](#pipeline-dimport-des-questions)
11. [Rôles et authentification](#rôles-et-authentification)
12. [Commandes utiles](#commandes-utiles)

---

## Contexte métier

Les étudiants préparent un examen de Halakha (loi juive) structuré autour de :

- **Parcours** (`parcours`) → **Sujets** (`sujet`) → **Simanim** (chapitres) → **Seifim** (sous-sections)
- Chaque question appartient à un ou plusieurs **sections de révision** (`exam_section` : `shulchan_aruch`, `tur`, etc.)
- La répétition espacée (algorithme FSRS-6 + calibration collective) adapte le calendrier de révision à chaque étudiant
- Un système de **points / combos / séries** (streak) gamifie la progression
- Un back-office permet à une équipe de **importateurs / validateurs** de gérer la banque de questions

---

## Stack technique

| Couche | Technologie |
|---|---|
| Serveur | Flask 3.0, Python 3.8+ |
| ORM / BDD | Flask-SQLAlchemy 3.1, SQLite (dev) / Postgres (prod) |
| Templates | Jinja2 (SSR, RTL) |
| Auth | Sessions Flask + Werkzeug (PBKDF2) |
| JS côté client | Vanilla JS (uniquement dans `static/js/chapitre.js`) |
| SRS | FSRS-6 maison (`fsrs.py`) + calibration collective (`calibration.py`) — sans dépendance externe |
| Dépendances | 3 paquets (`Flask`, `Flask-SQLAlchemy`, `Werkzeug`) |

Aucune dépendance externe (pas d'API tierce, pas d'IA, pas de CDN obligatoire).

---

## Installation rapide

```bash
cd smiha-flask

# 1. Installer les dépendances
python -m pip install -r requirements.txt

# 2. Initialiser la base de données + comptes de démo + questions d'exemple
python seed.py

# 3. Lancer le serveur de développement (debug + auto-reload)
python app.py
# → http://localhost:5000
```

### Comptes de démonstration

| Rôle | Email | Mot de passe |
|---|---|---|
| super_admin | bcbeneghmos@gmail.com | password123 |
| student | student@example.com | password123 |

> `seed.py` est idempotent à condition de partir d'une base vide. Pour tout remettre à zéro, supprimez `smiha.db` et relancez `python seed.py`. Un super_admin peut aussi utiliser le bouton **Réinitialiser la base** dans le dashboard admin.

---

## Configuration

Toutes les variables se trouvent dans `config.py` et sont surchargeables par variables d'environnement :

| Variable | Défaut | Description |
|---|---|---|
| `SECRET_KEY` | `"dev-change-me-in-production"` | Clé de signature des sessions Flask — **changer impérativement en prod** |
| `DATABASE_URL` | `sqlite:///smiha.db` | URL de connexion SQLAlchemy. Passer `postgresql+psycopg://...` pour Postgres |
| `SUPER_ADMIN_EMAIL` | `bcbeneghmos@gmail.com` | Email automatiquement promu `super_admin` à l'inscription |
| `FLASK_PORT` | `5000` | Port d'écoute (lu dans `app.py`) |

Exemple production :

```bash
export SECRET_KEY="votre-clé-aléatoire-longue"
export DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/smiha"
export SUPER_ADMIN_EMAIL="admin@votre-org.com"
```

---

## Structure du projet

```
smiha-flask/
├── app.py                  # Factory Flask : init DB, enregistrement blueprints, filtre to_hebrew
├── config.py               # Classe Config (variables d'env)
├── models.py               # 8 modèles SQLAlchemy
├── auth_helpers.py         # Session, g.user, @login_required, @staff_required
├── fsrs.py                 # Algorithme FSRS-6 (21 poids) + réglages produit (cap/warm-up/w7/priors)
├── calibration.py          # Calibration collective : latence z-score, HSHS, Elo, priors par item
├── points.py               # Calcul points / combos (3 formules : étude / jour / stabilité)
├── question_types.py       # Normalisation + validation des 4 types de questions
├── seed.py                 # Initialisation BDD + données de démo + item_stats
├── requirements.txt        # Flask, Flask-SQLAlchemy, Werkzeug
├── sample_questions.json   # 3 questions d'exemple (MC, TF, dropdown) — maintenir en sync avec question_types.py
│
├── blueprints/
│   ├── auth.py             # Landing page, /auth (login/signup), /logout
│   ├── student.py          # /app/* : onboarding, home, parcours, chapitre, profil, révision
│   ├── admin.py            # /admin/* : dashboard, import, validation, gestion utilisateurs
│   └── api.py              # POST /api/answer (cœur de la boucle d'apprentissage)
│
├── templates/
│   ├── base.html           # Layout HTML de base (lang="he" dir="rtl")
│   ├── landing.html
│   ├── auth.html
│   ├── student/            # onboarding, home, parcours, chapitre, revision, profil, settings
│   └── admin/              # login, denied, dashboard, users, user_detail, import, validate
│
├── static/
│   ├── css/styles.css      # Thème navy/indigo/ambre, utilitaires RTL
│   └── js/
│       ├── chapitre.js     # Lecteur de questions interactif (463 lignes, vanilla JS)
│       └── hebrew-calendar.js
│
├── scripts/
│   ├── sim_schedule.py         # Simulation d'évaluation : scénarios + options utilisateur
│   ├── sim_priors.py           # Démonstration du mélange des priors collectifs
│   ├── recompute_item_stats.py # Batch : recalcul autoritaire des agrégats/priors
│   ├── migrate_phase2.py       # Migration schéma Phase 2 (bases existantes)
│   └── migrate_approve_pending.py  # Approuve les questions "pending" historiques (bases existantes)
│
└── tests/
    ├── test_fsrs.py            # Tests du scheduler FSRS-6 + quick wins (runner autonome)
    └── test_calibration.py     # Tests de la calibration collective
```

---

## Modèle de données

### `users`
Compte de base. Méthodes utiles : `set_password()`, `check_password()`, `has_role(role)`, `is_staff()`.

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `email` | String (unique) | |
| `password_hash` | String | PBKDF2 via Werkzeug |
| `full_name` | String | |
| `created_at` | DateTime | |

Relations : `roles` (→ UserRole), `student_profile` (→ StudentProfile, 1:1)

---

### `user_roles`
Contrainte unique `(user_id, role)`. Valeurs de `role` : `"super_admin"`, `"importer"`, `"validator"`, `"student"`.

---

### `student_profiles`
| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID (FK users.id, PK) | |
| `preparation_goal` | String | `"discovery"` / `"serious"` / `"intensive"` |
| `target_stability` | Float | Seuil FSRS cible, défaut 0.90 |
| `exam_date` | Date | Date de l'examen (pression temporelle FSRS) |
| `section` | JSON | Liste de sections, ex. `["shulchan_aruch", "tur"]` |
| `total_points` | Integer | Cumulatif |
| `streak_days` | Integer | Jours consécutifs d'activité |
| `last_activity_date` | Date | Pour calcul du streak |
| `onboarded` | Boolean | False jusqu'à passage de /app/onboarding |

---

### `questions`

> Toute modification de ce tableau doit être reflétée dans la section [Format JSON des questions](#format-json-des-questions) et dans `sample_questions.json`.

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `text` | Text | Texte hébreu |
| `choices` | JSON | Options de réponse |
| `correct_answer` | String | |
| `explanation` | Text | Explication après réponse |
| `difficulty` | Integer | 1 (facile), 2 (moyen), 3 (difficile) |
| `section` | JSON | Liste de sections de révision |
| `question_type` | Enum | `multiple_choice`, `true_false`, `multiple_opinions_dropdown`, `practical_scenario` |
| `payload` | JSON | Structure spécifique au type |
| `status` | String | `"pending"` / `"approved"` / `"rejected"` — défaut `"approved"` (voir [règle de statut](#règle-métier--acceptation-par-défaut-et-signalement)) |
| `parcours` | String | Parcours d'apprentissage — valeurs dans `VALID_PARCOURS` (ex : `"bassar_bechalav"`) |
| `subject` | String | Sujet Halakhique en hébreu (ex : `"בשר בחלב"`) — champ JSON `sujet` à l'import |
| `siman` | Integer | Numéro de chapitre (entier positif, obligatoire) |
| `seif` | Integer | Numéro de sous-section (entier positif, obligatoire) |
| `hint` | Text | Indice (optionnel) |
| `source_ref` | String | Référence source |
| `tags` | JSON | Liste de tags libres (optionnel) |
| `created_by` / `validated_by` | FK users | |

Méthodes : `as_dict()`, `section_list()`.

---

### `fsrs_cards`
État de répétition espacée par paire `(user_id, question_id)`.

| Colonne | Type | Notes |
|---|---|---|
| `due_date` | Date (indexé) | Prochain passage en révision |
| `stability` | Float | Rétention estimée |
| `fsrs_difficulty` | Float | Difficulté FSRS (≠ `questions.difficulty`) |
| `reps` | Integer | Nombre de révisions |
| `lapses` | Integer | Nombre d'oublis |
| `state` | String | `"new"` / `"learning"` / `"review"` / `"relearning"` |
| `avg_response_time_ms` | Float | |
| `target_stability` | Float | Copié depuis StudentProfile à la création |

---

### `item_stats`
Agrégats **collectifs par question** (calibration Phase 2). Clé = `question_id`. Ne contient que
des agrégats (pas d'identification croisée d'utilisateur ; les RT bruts restent sur `user_answers`).

| Colonne | Type | Notes |
|---|---|---|
| `question_id` | UUID (FK questions.id, PK) | |
| `question_type` | String | Copié de la question |
| `hidden_difficulty` | Integer | `questions.difficulty` (1..3) — prior de contenu |
| `n_responses` / `n_correct` | Integer | Volumétrie (gating de confiance) |
| `accuracy` | Float | `n_correct / n_responses` |
| `log_rt_mean` / `log_rt_sd` | Float | μ/σ de `log(rt)` sur les réponses **correctes** |
| `elo_difficulty` | Float | Rating Elo courant de l'item (Rasch dynamique) |
| `elo_n_updates` | Integer | Nombre de mises à jour Elo (contrôle le K décroissant) |
| `d0_prior` | Float | Difficulté FSRS dérivée (1..10) |
| `s0_prior_good` | Float | S0 par item pour une 1re note « Good » |

Recalculé de façon autoritaire par `scripts/recompute_item_stats.py` (batch) ; l'Elo est mis à jour
en ligne à chaque réponse.

---

### `user_speed`
Distribution de vitesse de lecture par utilisateur (normalisation de latence). Clé = `user_id`.

| Colonne | Type | Notes |
|---|---|---|
| `user_id` | UUID (FK users.id, PK) | |
| `log_rt_mean` / `log_rt_sd` | Float | μ/σ de `log(rt)` sur toutes les réponses valides |
| `n_responses` | Integer | |

---

### `user_answers`
Trace de chaque réponse soumise. Ne jamais modifier rétroactivement — les champs de calibration
ci-dessous sont **ajoutés** (append-only), jamais réécrits.

Champs de calibration collective (Phase 2) : `z_item` (`(log rt − μ_item)/σ_item`), `z_user`
(normalisé pour la vitesse de lecture), `auto_grade` (note continue 1.0..4.0 dérivée de la latence).
`StudentProfile` porte aussi `elo_ability` (capacité Elo de l'apprenant).

---

### `progression`
Avancement par `(user_id, subject, siman)`. Marqué `"completed"` quand toutes les questions du chapitre sont répondues correctement.

---

### `question_edits`
Journal d'audit : chaque action d'un validateur (approve / correct / reject) est enregistrée avec diff JSON.

---

## Format JSON des questions

> **Règle** : ce format est la source de vérité pour l'import. Toute modification de `_validate_common()` dans `question_types.py` doit être reflétée ici **et** dans `sample_questions.json`.

### Champs communs à tous les types (obligatoires)

| Champ JSON | Type | Valeurs autorisées | Colonne DB |
|---|---|---|---|
| `type` | string | `multiple_choice`, `true_false`, `multiple_opinions_dropdown`, `practical_scenario` | `question_type` |
| `parcours` | string | `"bassar_bechalav"` (liste dans `VALID_PARCOURS`) | `parcours` |
| `sujet` | string | texte hébreu non vide | `subject` |
| `siman` | integer | > 0 | `siman` |
| `seif` | integer | > 0 | `seif` |
| `difficulty_level` | integer | 1, 2, 3 | `difficulty` |
| `exam_section` | string ou liste | `"shulchan_aruch"`, `"tur"`, … | `section` |

### Champ optionnel

| Champ JSON | Type | Description |
|---|---|---|
| `tags` | array of strings | Mots-clés libres (ex : `["המתנה", "מחלוקת"]`) |

### Champs spécifiques par type

#### `multiple_choice`
```json
{
  "type": "multiple_choice",
  "parcours": "bassar_bechalav",
  "sujet": "בשר בחלב",
  "siman": 89,
  "seif": 1,
  "difficulty_level": 1,
  "exam_section": "shulchan_aruch",
  "question_text": "כמה זמן יש להמתין בין אכילת בשר לחלב למנהג בני אשכנז?",
  "options": [
    { "number": 1, "text": "שעה אחת",       "is_correct": false },
    { "number": 2, "text": "שלוש שעות",     "is_correct": false },
    { "number": 3, "text": "שש שעות",       "is_correct": true  },
    { "number": 4, "text": "אין צורך להמתין", "is_correct": false }
  ],
  "explanation": "מנהג בני אשכנז להמתין שש שעות בין בשר לחלב.",
  "tags": ["המתנה"]
}
```
Règles : au moins 2 options, numérotées en séquence à partir de 1 (1, 2, 3, …) sans trou ni doublon, au moins une `is_correct: true`. Le nombre d'options n'est plus figé à 4 — `options` peut contenir autant de propositions que nécessaire. Plusieurs options peuvent être marquées `is_correct: true` — dans ce cas l'étudiant doit sélectionner toutes les bonnes réponses (sélection multiple) pour que la question soit comptée juste.

#### `true_false`
```json
{
  "type": "true_false",
  "parcours": "bassar_bechalav",
  "sujet": "בשר בחלב",
  "siman": 89,
  "seif": 2,
  "difficulty_level": 2,
  "exam_section": "shulchan_aruch",
  "statement_text": "מותר לאכול גבינה קשה מיד לאחר אכילת בשר.",
  "correct_answer": false,
  "explanation": "אסור לאכול חלב לאחר בשר עד שיעבור זמן ההמתנה."
}
```

#### `multiple_opinions_dropdown`
```json
{
  "type": "multiple_opinions_dropdown",
  "parcours": "bassar_bechalav",
  "sujet": "בשר בחלב",
  "siman": 89,
  "seif": 3,
  "difficulty_level": 3,
  "exam_section": "shulchan_aruch",
  "question_text": "מהי עמדת כל פוסק לגבי המתנה לאחר אכילת תבשיל שיש בו טעם בשר?",
  "dropdown_choices": ["צריך להמתין", "אין צריך להמתין"],
  "decisors": [
    { "id": "d1", "name": "השולחן ערוך", "correct_choice": "אין צריך להמתין" },
    { "id": "d2", "name": "הרמ\"א",       "correct_choice": "צריך להמתין"     }
  ],
  "explanation": "נחלקו הפוסקים בדין המתנה לאחר תבשיל בשרי.",
  "tags": ["מחלוקת פוסקים"]
}
```
Règles : ≥ 2 decisors, chaque `correct_choice` doit être dans `dropdown_choices`.

#### `practical_scenario`
Structure similaire à `multiple_choice` avec un champ `scenario_text` additionnel décrivant le contexte pratique.

---

## Générer des questions JSON avec une IA

> Cette section s'adresse à quiconque veut utiliser un LLM pour produire des questions en masse.  
> **Règle** : l'IA doit lire la section [Format JSON des questions](#format-json-des-questions) ci-dessus avant de générer quoi que ce soit — les contraintes y sont définitives.

### Prompt template

```
Tu es un expert en Halakha (loi juive). Génère [N] questions en hébreu
au format JSON valide pour l'application Smiha Path.

Contraintes impératives :
- Respecte scrupuleusement le format de la section "Format JSON des questions" du README
- Valeurs autorisées pour "parcours"  : "bassar_bechalav"
- Valeurs autorisées pour "exam_section" : "shulchan_aruch", "tur", "psikei_admur", "ptei_teshuva"
- Les valeurs de "exam_section" doivent être celles maîtrisées par le sujet traité
  (ex : une question qui couvre aussi le Tur → ["shulchan_aruch", "tur"])
- "siman" et "seif" sont des entiers > 0
- "difficulty_level" : 1 (facile), 2 (moyen), 3 (difficile)
- Tous les textes de questions, options et explications en hébreu

Sujet : [SUJET EN HÉBREU, ex. בשר בחלב]
Siman : [N]
Types à générer : [multiple_choice | true_false | multiple_opinions_dropdown]

Retourne uniquement un tableau JSON valide, sans texte avant ou après.
```

### Exemple de lot JSON valide

```json
[
  {
    "type": "multiple_choice",
    "parcours": "bassar_bechalav",
    "sujet": "בשר בחלב",
    "siman": 89,
    "seif": 1,
    "difficulty_level": 1,
    "exam_section": "shulchan_aruch",
    "question_text": "כמה זמן יש להמתין בין אכילת בשר לחלב למנהג בני אשכנז?",
    "options": [
      { "number": 1, "text": "שעה אחת",        "is_correct": false },
      { "number": 2, "text": "שלוש שעות",      "is_correct": false },
      { "number": 3, "text": "שש שעות",        "is_correct": true  },
      { "number": 4, "text": "אין צורך להמתין", "is_correct": false }
    ],
    "explanation": "מנהג בני אשכנז להמתין שש שעות בין בשר לחלב."
  },
  {
    "type": "true_false",
    "parcours": "bassar_bechalav",
    "sujet": "בשר בחלב",
    "siman": 89,
    "seif": 2,
    "difficulty_level": 2,
    "exam_section": ["shulchan_aruch", "tur"],
    "statement_text": "לדעת הטור, מותר לאכול גבינה קשה מיד לאחר בשר.",
    "correct_answer": false,
    "explanation": "גם לדעת הטור יש להמתין."
  },
  {
    "type": "multiple_opinions_dropdown",
    "parcours": "bassar_bechalav",
    "sujet": "בשר בחלב",
    "siman": 89,
    "seif": 3,
    "difficulty_level": 3,
    "exam_section": ["shulchan_aruch", "tur"],
    "question_text": "מהי עמדת כל פוסק לגבי המתנה לאחר תבשיל בשרי?",
    "dropdown_choices": ["צריך להמתין", "אין צריך להמתין"],
    "decisors": [
      { "id": "d1", "name": "השולחן ערוך", "correct_choice": "אין צריך להמתין" },
      { "id": "d2", "name": "הרמ\"א",       "correct_choice": "צריך להמתין"     }
    ],
    "explanation": "נחלקו הפוסקים בדין המתנה לאחר תבשיל בשרי."
  }
]
```

### Points de vigilance pour la génération IA

- **`exam_section` multi-valeur** : une question couvrant plusieurs sources doit lister toutes les sections pertinentes (`["shulchan_aruch", "tur"]`). Elle ne sera proposée qu'aux étudiants ayant **toutes** ces sections.
- **Validation à l'import** : tout lot est passé par `normalize_imported_question()` — les erreurs sont remontées ligne par ligne avant sauvegarde. Aucune question n'est importée si le lot contient une erreur.
- **Statut initial** : toute question importée arrive avec `status="approved"` et est immédiatement proposée aux étudiants ; elle ne repasse en `"pending"` que si un étudiant la signale (voir [règle de statut](#règle-métier--acceptation-par-défaut-et-signalement)).

---

## Routes et API

### Authentification (`/`)

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Landing page |
| GET/POST | `/auth` | Login ou signup étudiant (formulaire double mode) |
| GET | `/logout` | Déconnexion |

---

### Espace étudiant (`/app/*`) — `@login_required`

| Méthode | Route | Description |
|---|---|---|
| GET | `/app/` | Redirige vers onboarding ou home |
| GET/POST | `/app/onboarding` | Choix de l'objectif, date d'examen, sections |
| GET | `/app/home` | Dashboard : compte à rebours, cartes dues, streak, % préparation |
| GET | `/app/parcours` | Table des matières : sujet → simanim rétractables → seifim en chips hébraïques |
| GET | `/app/chapitre/<subject>/<siman>[/<seif>]` | Lecture d'un chapitre |
| GET | `/app/revision` | Hub de révision : 4 cartes (jour / siman / sujet / aléatoire) avec compteurs |
| GET | `/app/revision/jour` | Révision du jour : cartes dues (répétition espacée FSRS) |
| GET | `/app/revision/siman` | Liste des simanim déjà appris, groupés par sujet |
| GET | `/app/revision/siman/<subject>/<siman>` | Session de révision sur un siman déjà appris |
| GET | `/app/revision/sujet` | Liste des tags (`Question.tags`) ayant ≥ 3 cartes déjà apprises |
| GET | `/app/revision/sujet/<tag>` | Session de révision sur toutes les cartes déjà apprises portant ce tag |
| GET | `/app/revision/aleatoire` | Session de révision aléatoire (max 10 cartes déjà apprises, retirée à chaque visite) |
| POST | `/app/advance-revisions` | Avance toutes les cartes dues de 1 jour (outil de test) |
| POST | `/app/reset-progress` | Efface UserAnswer + FsrsCard + Progression (nucléaire) |
| GET | `/app/profil` | Profil : total réponses, précision % |
| GET/POST | `/app/settings` | Modifier date examen, target_stability, sections |
| GET | `/app/today-stats` | JSON : points du jour, cartes révisées, précision |

---

### Back-office (`/admin/*`) — `@staff_required`

| Méthode | Route | Description |
|---|---|---|
| GET/POST | `/admin/login` | Authentification staff |
| GET | `/admin/` ou `/admin/dashboard` | Comptages par statut, répartition par sujet |
| GET | `/admin/users` | Liste étudiants + nombre de cartes |
| GET | `/admin/users/<user_id>` | Détail étudiant (progression, stabilité, réponses) |
| GET/POST | `/admin/import` | Import JSON (prévisualisation → confirmation) |
| GET/POST | `/admin/validate` | File de questions `pending` (incluant les questions signalées) : approuver / rejeter |
| POST | `/admin/validate/approve-all` | Approuve en un clic toutes les questions `pending` (bouton « אשר הכל » de la file) |
| GET | `/admin/questions` | Recherche/édition de toutes les questions — filtres `status`, `type`, `parcours`, `siman`, `q` (texte libre) |
| POST | `/admin/questions/<qid>/edit` | Sauvegarde / approuve / rejette une question depuis `/admin/questions` |
| POST | `/admin/reset-db` | **super_admin uniquement** — efface et recrée toutes les tables (confirmation texte `"RESET"` requise) |

---

### API JSON (`/api/*`) — `@login_required`

#### `POST /api/answer`

Corps JSON attendu :
```json
{
  "question_id": "uuid",
  "given_answer": "texte de la réponse",
  "response_time_ms": 8500,
  "combo": 3,
  "mode": "revision_daily"
}
```

`mode` (optionnel, défaut `"study"`) sélectionne la formule de points appliquée (voir
[Système de points](#système-de-points-pointspy)) :
- `"study"` (ou champ omis) — étude normale (`/app/chapitre/…`) : `compute_points`
- `"revision_daily"` — révision du jour (`/app/revision/jour`) : `compute_daily_points`, cappé à 30
- `"revision_siman"` / `"revision_sujet"` / `"revision_random"` — révisions volontaires
  (`/app/revision/siman/…`, `/app/revision/sujet/…`, `/app/revision/aleatoire`) : `compute_stability_points`, cappé à 8

Réponse JSON :
```json
{
  "is_correct": true,
  "correct_key": "texte correct",
  "points": 24,
  "combo": 4,
  "streak": 7,
  "total_points": 1240,
  "explanation": "...",
  "rating_badge": "⚡ Rapide !",
  "daily_bonus": 0
}
```

`daily_bonus` — bonus de complétion quotidienne (150 + 20 par jour de série consécutive). Toujours
`0` sauf quand `mode == "revision_daily"` **et** que cette réponse vide complètement la file des
cartes dues du jour (`FsrsCard.due_date <= aujourd'hui`) — auquel cas il est ajouté à `total_points`
en plus de `points`.

**Effets de bord** (dans l'ordre) :
1. Enregistre un `UserAnswer` (avec `z_item`, `z_user`, `auto_grade`)
2. Crée ou met à jour la `FsrsCard` (scheduling FSRS-6, prior collectif par item si carte neuve)
3. Met à jour la calibration collective : Elo (`ItemStats.elo_difficulty`, `StudentProfile.elo_ability`),
   compteurs et distributions log-RT (`ItemStats`, `UserSpeed`)
4. Met à jour (ou crée) la `Progression` du chapitre
5. Met à jour `StudentProfile` : `total_points`, `streak_days`, `last_activity_date`
6. Si `mode == "revision_daily"` et que la file du jour vient d'être vidée : ajoute le bonus de
   complétion quotidienne (`daily_bonus`) à `total_points` et met à jour `daily_completion_streak` /
   `last_daily_completion_date`

#### `POST /api/report`

Signalement d'une question par un étudiant, depuis le bouton 🚩 du lecteur (`chapitre.js`).

Corps JSON attendu :
```json
{
  "question_id": "uuid",
  "reason": "motif optionnel du signalement"
}
```

Réponse JSON : `{"ok": true}`. Effet de bord : `Question.status` repasse à `"pending"` et une
`QuestionEdit` (`action="reported"`, `note=reason`) est journalisée. La question redevient
invisible pour tous les étudiants tant qu'un validateur ne l'a pas retraitée dans `/admin/validate`.

---

## Logique métier clé

### Algorithme FSRS-6 (`fsrs.py`)

Port maison de l'algorithme publié **FSRS-6** (21 poids `w0–w20`, valeurs par défaut vérifiées
contre `py-fsrs`), sans dépendance externe. La courbe d'oubli est personnalisable via `w20`
(`DECAY = −w20`), la difficulté utilise le *linear damping* + réversion à la moyenne vers `D0(Easy)`,
et un lapse ne peut jamais augmenter la stabilité (cap FSRS-6).

- **Rating automatique** (pas de choix utilisateur) : déduit de l'exactitude + de la vitesse.
  - Par défaut, la vitesse est normalisée par **z-score** collectif (voir `calibration.py`). Tant qu'un
    item/utilisateur n'a pas assez de données, on retombe sur des seuils absolus par difficulté
    (fallback rétro-compatible) :
    - Difficulté 1 : rapide < 5 s, moyen < 15 s · Difficulté 2 : < 10 s / < 25 s · Difficulté 3 : < 18 s / < 40 s
  - Rating 1 = mauvais, 2 = lent, 3 = moyen, 4 = rapide.
- **Rétentabilité** : `R(t, S) = (1 + FACTOR × t / S)^DECAY`, avec `DECAY = −w20`.
- **Intervalle optimal** : `interval = S / FACTOR × (target^(1/DECAY) − 1)` (≈ `S × 0.40` à `target = 0.95`).
- **Pression examen** : compression continue quand l'examen est à moins de 90 jours.
  - Facteur `max(0.30, days_left / 90)` — linéaire ; plafond absolu : l'intervalle ne dépasse jamais `days_left`.
- **Tri des révisions** : cartes présentées par stabilité croissante (moins bien mémorisée en premier).
- **`target_stability`** configurable par étudiant — 3 niveaux (`0.92` יעיל / `0.95` מאוזן / `0.96` מעמיק).
- **Intervalle max** : 365 jours.

#### Réglages produit (constantes nommées en tête de `fsrs.py`)

Ces garde-fous corrigent deux modes d'échec observés ; ils sont **réglables** et à valider
empiriquement (voir `scripts/sim_schedule.py` pour balayer scénarios + options) :

- **`CAP_FIRST`** (4 j) — plafond du tout premier intervalle : une carte réussie au 1er coup ne
  « disparaît » plus une semaine.
- **`WARMUP_INTERVALS`** (`[1, 3, 7]`) — rampe conservatrice sur les premiers passages avant que FSRS
  ne pilote pleinement.
- **`W7_FLOOR`** (0.15) — plancher sur la réversion à la moyenne (le défaut FSRS-6 `w7 = 0.001` est
  inerte) : une carte ratée au départ revient vite à une difficulté moyenne.
- **Adoucissement du 1er contact** (`soften_first_contact`) — sur la 1re exposition, une réponse
  correcte ne descend jamais sous « Good » (la latence y reflète la lecture, pas la mémoire).

#### Calibration collective (`calibration.py`, Phase 2)

Priors de difficulté **par item** issus des réponses de tous les utilisateurs, injectés dans `S0`/`D0`
d'une carte neuve — **toujours par mélange, jamais en substitution** :

```
S0_card = (1 − α) · S0_fsrs + α · s0_prior_item
D0_card = (1 − α) · D0_fsrs + α · d0_prior_item
```

- `α` (poids de mélange) monte avec la confiance (`n_responses`) mais est **plafonné à
  `ALPHA_MAX = 0.6`** : le collectif *incline* la difficulté sans jamais la dicter à 100 %.
- Gating : `< 30` réponses → prior de contenu léger (`hidden_difficulty`) ; `30–100` → Elo provisoire
  (K décroissant) ; `≥ 100` → prior fiable (α = `ALPHA_MAX`).
- **Normalisation de latence** : `z_item = (log rt − μ_item)/σ_item` (neutralise la longueur de
  question), `z_user` (neutralise la vitesse de lecture), avec winsorisation (RT hors `[400 ms, 120 s]`).
- **Elo dynamique** (Rasch) : met à jour ensemble `elo_difficulty` (item) et `elo_ability` (user),
  score intégrant exactitude + latence (règle HSHS).

### Système de points (`points.py`)

Trois formules distinctes selon le `mode` transmis à `POST /api/answer` (voir
[POST /api/answer](#post-apianswer)) — **aucun multiplicateur de streak** : le seul mécanisme lié à
la régularité est le bonus de complétion quotidienne explicite (`daily_bonus`, calculé dans
`blueprints/api.py`, pas dans `points.py`), pour éviter un double comptage.

Dans les trois formules : mauvaise réponse → 0 point, combo réinitialisé à 0 côté client.
`combo` (multiplicateur commun) : `{2: ×1.1, 3: ×1.2, 4: ×1.3, 5+: ×1.5}`.

#### `compute_points` — étude normale (`mode` omis ou `"study"`)

```
points = (base + bonus_difficulté + bonus_vitesse) × multiplicateur_combo

base = 10
bonus_difficulté : {1: +2, 2: +4, 3: +6}
bonus_vitesse    : {rapide: +5, moyen: +2, lent: 0}
```

#### `compute_daily_points` — révision du jour (`mode="revision_daily"`)

```
points = min(30, base × multiplicateur_combo)
base    = min(30, round(10 × log10(jours_depuis_dernière_réponse + 1)))
```

Proportionnel au temps écoulé depuis la dernière réponse (jamais à la stabilité), pour qu'échouer
une carte exprès ne puisse jamais augmenter artificiellement les points futurs. Courbe
logarithmique (plafond 30), voir `blueprints/api.py` pour le calcul de `jours_depuis_dernière_réponse`.

#### `compute_stability_points` — révision par siman / sujet / aléatoire (`mode="revision_siman"` / `"revision_sujet"` / `"revision_random"`)

```
points = min(8, base × multiplicateur_combo)
base    = min(8, round(8 × (1 − retrievability)))
```

Inversement proportionnel à la `retrievability` FSRS (`fsrs.retrievability`) — plus la carte est
« fraîche » en mémoire, moins la révision volontaire rapporte de points (plafond 8).

### Validation des questions (`question_types.py`)

`normalize_imported_question()` valide et normalise les 4 types à l'import :

| Type | Règles spécifiques |
|---|---|
| `multiple_choice` | 4 options numérotées, une seule bonne réponse |
| `true_false` | Booléen simple |
| `multiple_opinions_dropdown` | ≥ 2 "decisors" (opinions), choix parmi liste |
| `practical_scenario` | QCM avec contexte de scénario |

Valide aussi les **champs communs obligatoires** : `parcours` (valeur dans `VALID_PARCOURS`), `sujet` (texte hébreu non vide), `siman` (entier > 0), `seif` (entier > 0), `difficulty_level` (1, 2 ou 3).

### Filtre Jinja2 `to_hebrew` (`app.py`)

Convertit un entier en notation hébraïque (gematria) avec geresh/gershayim :
- `1` → `א׳`, `10` → `י׳`, `89` → `פ״ט`
- Cas spéciaux : 15 → `ט״ו`, 16 → `ט״ז` (évite les combinaisons יה / יו)
- Utilisé dans les templates : `{{ s.siman | to_hebrew }}`, `{{ sf.seif | to_hebrew }}`

### Page Parcours (`/app/parcours`)

- En-tête par **sujet** (ex : `בשר בחלב`) avec compteur de simanim et questions
- Chaque **siman** est un `<details>` rétractable avec son numéro en hébreu (פ״ט, צ׳, …)
- À l'intérieur : **seifim** en chips cliquables avec indicateur ✓ si complété et barre de progression
- Aucun siman n'est verrouillé — l'étudiant accède librement à n'importe quel seif

### Sections d'examen

Les sections représentent les **sources halakhiques** étudiées. Chaque question est taguée avec une ou plusieurs sections ; chaque étudiant choisit les sources qu'il étudie à l'onboarding (et peut les modifier dans les paramètres).

#### Sections valides (`VALID_SECTIONS` dans `question_types.py`)

| Valeur | Nom | Contenu |
|---|---|---|
| `shulchan_aruch` | Shoulhan Arouh | Texte du Shoulhan Arouh (Rav Yossef Karo) + Rama + commentateurs principaux (Sha'h, Taz…) — **toujours inclus, obligatoire** |
| `tur` | Tour | Texte du Tour (Rav Yaakov ben Asher) + Beit Yossef + Darkei Moshe |
| `psikei_admur` | Piskei Admour HaZaken | Décisions du Admour HaZaken (Rabbi Shneur Zalman de Liadi) + minhag Chabad |
| `ptei_teshuva` | Pitchei Teshouva | Commentaire Pitchei Teshouva + Aharonim complémentaires |

#### Règle de filtrage — ALL (sous-ensemble strict)

Une question n'est proposée à un étudiant que si **toutes** ses sections sont incluses dans les sections de l'étudiant.

Formellement : `question.sections ⊆ student.sections`

```
question.section = ["shulchan_aruch", "tur"]

étudiant A sections = ["shulchan_aruch"]          → question invisible (tur manquant)
étudiant B sections = ["shulchan_aruch", "tur"]   → question visible ✓
```

Implémenté dans `allowed_sections()` + `question_in_sections()` (`blueprints/student.py`).

#### Règle métier : `shulchan_aruch` toujours inclus

`shulchan_aruch` est automatiquement injecté dans l'ensemble autorisé de tout étudiant par `allowed_sections()`, même s'il n'est pas explicitement dans `StudentProfile.section`. À l'onboarding et dans les paramètres, la case correspondante est verrouillée et toujours cochée.

### Règle métier : acceptation par défaut et signalement

Toute question est **acceptée par défaut** (`status="approved"` dès sa création — import ou seed), et donc immédiatement proposée aux étudiants. Il n'y a plus de file d'attente systématique avant mise en ligne.

- **Signalement étudiant** — dans le lecteur de questions (`chapitre.js`), un bouton 🚩 (icône drapeau) permet à l'étudiant de signaler une question douteuse, avec un motif optionnel. Cela appelle `POST /api/report` (`blueprints/api.py`) qui repasse la question en `status="pending"` et journalise l'action dans `question_edits` (`action="reported"`, `note` = motif). La question disparaît alors du parcours de tous les étudiants jusqu'à décision.
- **Décision de l'admin** — la question signalée réapparaît dans la file `/admin/validate` (statut `pending`, la vue par défaut) exactement comme une question nouvellement importée ; le validateur l'approuve ou la rejette normalement.
- **Base existante** — `scripts/migrate_approve_pending.py` bascule en `approved` les questions `pending` d'une base existante (celles jamais explicitement rejetées) pour aligner les anciennes données sur ce nouveau défaut.

---

## Pipeline d'import des questions

```
Importer (JSON) → Prévisualisation (normalize_imported_question) → Sauvegarde status="approved"
                                                                          ↓
                                                        (visible immédiatement aux étudiants)
                                                                          ↓
                                        Étudiant signale (🚩) → status="pending"
                                                                          ↓
Validateur → /admin/validate → Édite métadonnées (subject/siman/seif/parcours, difficulté, tags)
                                    ↓                        ↓
                              Approuve → status="approved"   Rejette → status="rejected" + note
                                    ↓
                         Audit enregistré dans question_edits (action="approved"/"rejected"/"reported")
```

Le format JSON d'import accepte un tableau d'objets. Chaque objet est normalisé par `question_types.py`. Les erreurs de validation sont remontées ligne par ligne dans la prévisualisation — aucune question n'est importée si le lot contient des erreurs.

---

## Rôles et authentification

**Mécanisme** : session Flask (`session["user_id"]`) + chargement dans `g.user` avant chaque requête via `@app.before_request`.

| Rôle | Accès | Attribution |
|---|---|---|
| `student` | `/app/*` | Par défaut à l'inscription |
| `importer` | `/admin/*` + import JSON | Manuel (super_admin) |
| `validator` | `/admin/*` + validation | Manuel (super_admin) |
| `super_admin` | Tout + reset DB | Auto si email = `SUPER_ADMIN_EMAIL`, sinon manuel |

Décorateurs disponibles dans `auth_helpers.py` :
- `@login_required` — redirige vers `/auth` si non connecté
- `@staff_required` — redirige vers `/admin/denied` si pas de rôle staff

Un utilisateur peut avoir plusieurs rôles simultanément (table `user_roles`).

---

## Commandes utiles

```bash
# Réinitialiser la base de données (repart de zéro)
rm smiha.db && python seed.py          # Linux/Mac
Remove-Item smiha.db; python seed.py   # PowerShell

# Lancer en mode développement (debug + auto-reload)
python app.py

# SRS / calibration collective (Phase 2)
python -m scripts.sim_schedule          # évaluer le scheduler : scénarios + options utilisateur
python -m scripts.sim_priors            # visualiser le mélange des priors (jamais 100 %)
python -m scripts.recompute_item_stats  # batch : recalcul autoritaire des agrégats/priors
python -m scripts.migrate_phase2        # migration schéma sur une base EXISTANTE (prod)
python -m scripts.migrate_approve_pending  # approuve les questions "pending" historiques (base EXISTANTE)

# Tests (sans pytest requis)
python tests/test_fsrs.py
python tests/test_calibration.py

# Vérifier l'état de la base en SQLite
sqlite3 smiha.db ".tables"
sqlite3 smiha.db "SELECT email, role FROM users JOIN user_roles ON users.id=user_roles.user_id;"

# Variables d'env pour la prod (Bash)
export SECRET_KEY="..." DATABASE_URL="postgresql+psycopg://..." SUPER_ADMIN_EMAIL="..."
python app.py

# Git — sauvegarder les credentials GitHub une seule fois (ex. sur PythonAnywhere)
git config --global credential.helper store
```

---

## Points d'attention pour un futur développeur

- **RTL** : tous les templates ont `lang="he" dir="rtl"`. Ajouter du HTML sans tester en hébreu peut casser l'alignement.
- **`section` est une liste JSON** sur `StudentProfile` et `Question`. Utiliser `question.section_list()` pour la lire de façon cohérente.
- **Filtrage strict des sections** : une question n'est proposée que si **toutes** ses sections sont dans celles de l'étudiant (`question.sections ⊆ student.sections`). Exemple : une question `["shulchan_aruch", "tur"]` est invisible pour un étudiant qui n'a que `shulchan_aruch`. Pas d'alias, pas d'implicite (sauf `shulchan_aruch` toujours injecté par `allowed_sections()`).
- **Champs obligatoires des questions** : `parcours`, `sujet`/`subject`, `siman`, `seif` sont requis depuis l'import. Modifier leur validation dans `question_types.py` **doit** s'accompagner d'une mise à jour de ce README et de `sample_questions.json`.
- **`VALID_PARCOURS`** dans `question_types.py` est la liste des parcours autorisés. Ajouter un parcours = ajouter ici + mettre à jour ce README.
- **Tests** : le cœur SRS est couvert par `tests/test_fsrs.py` et `tests/test_calibration.py`
  (runner autonome, pytest optionnel) ; le reste de l'app n'a pas de couverture — vérifier les
  régressions manuellement et étendre les tests avant d'ajouter une feature complexe.
- **FSRS-6 — réglages produit** : `CAP_FIRST`, `WARMUP_INTERVALS`, `W7_FLOOR`, `ALPHA_MAX` s'écartent
  volontairement des défauts FSRS. Ils doivent être **validés empiriquement** sur les logs réels
  (rétention cible vs réelle), pas figés. `scripts/sim_schedule.py` sert à les balayer.
- **Calibration collective** : les priors par item ne remplacent jamais FSRS à 100 % (mélange
  plafonné à `ALPHA_MAX`). L'Elo est mis à jour en ligne ; `scripts/recompute_item_stats.py` est la
  source autoritaire des μ/σ de latence — le lancer en batch (cron nocturne) pour la stabilité.
- **Migration** : sur une base existante, lancer `python -m scripts.migrate_phase2` (ajoute les
  colonnes + tables Phase 2). Une base neuve (`python seed.py`) est déjà au bon schéma.
- **Acceptation par défaut** : `Question.status` vaut `"approved"` par défaut (voir
  [règle métier](#règle-métier--acceptation-par-défaut-et-signalement)). Sur une base existante,
  lancer `python -m scripts.migrate_approve_pending` pour approuver les questions `pending`
  historiques.
- **`FsrsCard.target_stability`** est copié depuis `StudentProfile` à la création de la carte. Modifier le profil étudiant ne met pas à jour les cartes existantes — prévu par design.
- **`/app/reset-progress`** efface `UserAnswer`, `FsrsCard`, `Progression` sans confirmation supplémentaire. Protéger en prod si nécessaire.
- **`/admin/reset-db`** efface **toutes** les tables et déconnecte l'utilisateur. Réservé au `super_admin`, requiert la saisie du mot `"RESET"` en confirmation.
- **`seed.py`** insère les comptes de démo avec des mots de passe en clair dans le code. Ne pas utiliser en prod.
- **`chapitre.js`** gère l'état du combo côté client et l'envoie avec chaque réponse. Le serveur fait confiance à cette valeur — un client malveillant pourrait l'altérer.
