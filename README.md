# קניין הלכה (Flask + SQLAlchemy)

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
> - Back-office : `/admin/dashboard`, `/admin/import`, `/admin/questions`
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
13. [Service worker & mise à jour automatique](#service-worker--mise-à-jour-automatique)
14. [Déploiement continu (PythonAnywhere)](#déploiement-continu-pythonanywhere)

---

## Contexte métier

Les étudiants préparent un examen de Halakha (loi juive) structuré autour de :

- **Parcours** (`parcours`) → **Simanim** (chapitres) → **Sujets** (`sujet` : thème traité dans le siman, pouvant couvrir plusieurs seifim). Le **seif** de chaque question est conservé à titre indicatif.
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
| `PROTECTED_SUPER_ADMIN_EMAIL` | `bcbeneghmos@gmail.com` | Compte propriétaire protégé, fixé dans le code et non surchargeable : rôle `super_admin` réparé au démarrage, retrait/suppression bloqués |
| `SUPER_ADMIN_EMAIL` | `bcbeneghmos@gmail.com` | Email additionnel automatiquement promu `super_admin` à l'inscription ; ne remplace jamais le compte propriétaire protégé |
| `ALLOWED_SIGNUP_EMAILS` | *(vide → `SUPER_ADMIN_EMAIL` seul)* | Liste blanche d'emails autorisés à s'inscrire via `/auth` (séparés par des virgules). Restriction temporaire — voir [Rôles et authentification](#rôles-et-authentification). Ne s'applique pas aux comptes créés par `seed.py` |
| `FLASK_PORT` | `5000` | Port d'écoute (lu dans `app.py`) |
| `GITHUB_WEBHOOK_SECRET` | `None` | Secret HMAC-SHA256 partagé avec le webhook GitHub — voir [Déploiement continu](#déploiement-continu-pythonanywhere). `None` désactive l'endpoint |
| `BACKUP_DIR` | `db_backups/` | Dossier privé des sauvegardes administrées |
| `EMERGENCY_SQL_API_ENABLED` | `0` | Active explicitement l'API SQL d'urgence ; laisser désactivé hors incident |
| `EMERGENCY_SQL_API_MAX_TTL_MINUTES` | `60` | Durée maximale d'un jeton SQL d'urgence (5 à 60 minutes) |
| `PYTHONANYWHERE_USERNAME` | `None` | Nom d'utilisateur PythonAnywhere — seul requis pour le reload automatique via `touch` du fichier WSGI (fonctionne sur tous les plans, y compris gratuit) |
| `PYTHONANYWHERE_DOMAIN` | `<USERNAME>.pythonanywhere.com` | Domaine du web app à recharger (à surcharger pour un domaine personnalisé) |
| `PYTHONANYWHERE_API_TOKEN` | `None` | Token API PythonAnywhere (Account → API Token) — optionnel, fallback si le `touch` échoue ; **403 sur les comptes gratuits** (Beginner), réservé aux plans payants |

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
├── models.py               # 13 modèles SQLAlchemy
├── auth_helpers.py         # Session, g.user, @login_required, @staff_required
├── fsrs.py                 # Algorithme FSRS-6 (21 poids) + réglages produit (cap/warm-up/w7/priors)
├── calibration.py          # Calibration collective : latence z-score, HSHS, Elo, priors par item
├── points.py               # Calcul points / combos (3 formules : étude / jour / stabilité)
├── question_types.py       # Normalisation + validation des 3 types de questions
├── subjects.py             # Lookup-or-create / renommage (avec fusion) des Subject par ID
├── seed.py                 # Initialisation BDD + données de démo + item_stats
├── requirements.txt        # Flask, Flask-SQLAlchemy, Werkzeug
├── sample_questions.json   # 3 questions d'exemple (MC, TF, dropdown) — maintenir en sync avec question_types.py
│
├── blueprints/
│   ├── auth.py             # Landing page, /auth (login/signup), /logout
│   ├── student.py          # /app/* : onboarding, home, parcours, chapitre, profil, révision
│   ├── admin.py            # /admin/* : dashboard, import, validation, gestion utilisateurs
│   ├── api.py              # POST /api/answer (cœur de la boucle d'apprentissage)
│   └── webhook.py          # POST /webhook/deploy : git pull auto sur push GitHub (voir Déploiement continu)
│
├── templates/
│   ├── base.html           # Layout HTML de base (lang="he" dir="rtl")
│   ├── landing.html
│   ├── auth.html
│   ├── student/            # onboarding, home, parcours, chapitre, revision, profil, settings
│   └── admin/              # login, denied, dashboard, users, user_detail, import, questions, topics
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
│   ├── recompute_item_stats.py # Batch : recalcul autoritaire des agrégats/priors + rollup rétention
│   ├── migrate_phase2.py       # Migration schéma Phase 2 (bases existantes)
│   ├── migrate_predicted_r.py  # Migration : ajoute user_answers.predicted_r (bases existantes)
│   ├── migrate_approve_pending.py  # (historique) Approuve les questions "pending" — ancien défaut
│   ├── migrate_requeue_approved.py # Rebascule les questions "approved" en "pending" — nouveau défaut (bases existantes)
│   ├── migrate_multi_parcours.py   # Crée student_parcours + backfill legacy (bases existantes)
│   ├── migrate_subjects.py         # Crée la table subjects + backfill subject_id (bases existantes)
│   ├── simulate_multi_parcours.py  # Base de démo isolée « plusieurs parcours entamés » (build/serve)
│   └── screenshot_sim.py           # Captures d'écran de la simulation (Playwright) → screenshots/simulations/
│
└── tests/
    ├── test_fsrs.py            # Tests du scheduler FSRS-6 + quick wins (runner autonome)
    ├── test_calibration.py     # Tests de la calibration collective
    └── test_multi_parcours.py  # Tests multi-parcours : bonus par parcours, sélecteur, pression examen
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

Le compte `bcbeneghmos@gmail.com` est l'identité propriétaire protégée. Tant qu'il existe,
son rôle `super_admin` est vérifié et réparé à chaque démarrage. Sur SQLite, des triggers
interdisent également la suppression directe de sa ligne, la modification de son email et
le retrait ou changement de son rôle `super_admin`. Un reset applicatif conserve son ID,
son mot de passe et son rôle.

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
| `exam_date` | Date | **DEPRECATED** — remplacé par `student_parcours.exam_date` (une date par parcours). Conservé en base pour migration/rollback, plus jamais lu ni écrit |
| `section` | JSON | Liste de sections, ex. `["shulchan_aruch", "tur"]` |
| `total_points` | Integer | Cumulatif |
| `streak_days` | Integer | Jours consécutifs d'activité |
| `last_activity_date` | Date | Pour calcul du streak |
| `daily_completion_streak` / `last_daily_completion_date` | Integer / Date | **DEPRECATED** — remplacés par les champs homonymes de `student_parcours` (série par parcours) |
| `onboarded` | Boolean | False jusqu'à passage de /app/onboarding |

---

### `student_parcours`
Parcours **activé** par un étudiant — une ligne = parcours actif. Contrainte unique `(user_id, parcours)`. La désactivation (depuis les paramètres) **supprime** la ligne : date et série quotidienne perdues (assumé) ; les `fsrs_cards` du parcours restent en base, simplement masquées tant qu'il n'est pas réactivé.

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `user_id` | FK users.id (index) | |
| `parcours` | String(64) | Valeur de `VALID_PARCOURS` |
| `exam_date` | Date (nullable) | Date du מבחן de CE parcours — pilote la pression FSRS des questions du parcours ; NULL = pas de pression |
| `daily_completion_streak` | Integer | Série de complétion quotidienne **de ce parcours** |
| `last_daily_completion_date` | Date | Garde anti-double bonus, par parcours |
| `created_at` | DateTime | Date d'activation — sert de point de départ à la barre de préparation (`prep_pct`) |

Un profil `onboarded` sans aucune ligne (base pré-migration) est automatiquement rattaché à `bassar_bechalav` par le fallback de `get_active_parcours()` (`blueprints/student.py`), en copiant les champs dépréciés de `student_profiles`.

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
| `question_type` | Enum | `multiple_choice`, `true_false`, `multiple_opinions_dropdown` |
| `payload` | JSON | Structure spécifique au type |
| `status` | String | `"pending"` / `"approved"` / `"a_revoir"` / `"rejected"` — défaut `"pending"` (voir [règle de statut](#règle-métier--file-dattente-par-défaut-et-signalement)) |
| `parcours` | String | Parcours d'apprentissage — valeurs dans `VALID_PARCOURS` (ex : `"bassar_bechalav"`) |
| `subject_id` | FK subjects.id (nullable) | Sujet traité **dans le siman** — voir [`subjects`](#subjects) ci-dessous. Le champ JSON `sujet` (texte hébreu) reste le format d'import ; il est résolu vers cet ID par `get_or_create_subject()` (`subjects.py`), jamais stocké tel quel |
| `siman` | Integer | Numéro de chapitre (entier positif, obligatoire) |
| `seif` | Integer | Numéro de sous-section (entier positif, obligatoire) |
| `hint` | Text | Indice (optionnel) |
| `source_ref` | String | Référence source |
| `tags` | JSON | Liste de tags libres (optionnel) |
| `created_by` / `validated_by` | FK users | |

Méthodes : `as_dict()` (inclut `subject_id` et `subject` — le titre résolu via la relation `Subject`, ou `None`), `section_list()`.

---

### `subjects`

Un sujet (« נושא ») regroupe les questions d'un même thème **à l'intérieur d'un siman**. Introduit pour découpler la clé de regroupement (stable) de son intitulé affiché (renommable) — avant, `questions.subject` était le texte lui-même, et le renommer exigeait un chercher/remplacer sur toutes les cartes qui le partageaient.

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Référencé par `questions.subject_id` et `progression.subject_id` |
| `parcours` | String(64) | |
| `siman` | Integer | |
| `title` | String(255) | Titre hébreu affiché à l'étudiant (`/app/parcours`, en-tête de session) |
| `created_at` | DateTime | |

Contrainte unique `(parcours, siman, title)`. Gestion dans `subjects.py` :
- `get_or_create_subject(parcours, siman, title)` — lookup-or-create par correspondance exacte, appelé à chaque import/édition de question (le format JSON continue de porter `sujet` en texte libre, voir [Format JSON des questions](#format-json-des-questions)) ;
- `rename_subject(subject_id, new_title)` — renomme le titre affiché (`POST /admin/subjects/rename`, une seule ligne modifiée). Si le nouveau titre entre en collision avec un autre sujet du même siman, **fusionne** les deux : questions et `Progression` du sujet source sont réassignées au sujet cible, puis le sujet source est supprimé — reproduit l'ancien comportement de fusion implicite (deux textes renommés vers la même valeur finissaient dans le même groupe).

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

Champ d'instrumentation de rétention : `predicted_r` — la rétrievabilité **prédite par FSRS au
moment de cette révision** (stabilité pré-mise-à-jour + jours écoulés). `NULL` pour une carte pas
encore engagée par FSRS (aucune prédiction à noter). Comparé à `is_correct`, il permet de mesurer
a posteriori la **rétention réelle vs prédite** (log loss, true retention) — voir
[Instrumentation de la rétention](#instrumentation-de-la-rétention). La colonne est ajoutée
automatiquement au démarrage sur une base existante (`app.py::_ensure_additive_columns`,
voir [note sur les migrations additives](#note--colonnes-additives-appliquées-au-démarrage)) ;
`python -m scripts.migrate_predicted_r` reste disponible pour l'appliquer sans redémarrer l'app.

---

### `progression`
Avancement par `(user_id, subject_id)` — `subject_id` implique déjà le siman (voir [`subjects`](#subjects), plus de colonne `siman` séparée ici). Marqué `"completed"` quand toutes les questions du sujet sont répondues correctement.

---

### `question_edits`
Journal d'audit : chaque action d'un validateur (approve / correct / reject) est enregistrée avec diff JSON.

---

### `question_reports`
Signalement **personnel** d'une question par un étudiant simple (aucun rôle staff). Tant que `status="open"`,
la question reste `approved` globalement mais est retirée **uniquement** pour `reporter_id` (voir
[règle de signalement](#règle-métier--file-dattente-par-défaut-et-signalement)).

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `question_id` | FK questions.id | |
| `reporter_id` | FK users.id | Étudiant qui a signalé |
| `reason` | Text | Motif optionnel |
| `status` | String | `"open"` / `"confirmed"` (retirée pour tout le monde) / `"dismissed"` (signalement injustifié, redevient visible pour le signaleur) |
| `resolved_by` | FK users.id | Validateur/super_admin ayant tranché |
| `resolved_at` | DateTime | |
| `created_at` | DateTime | |

---

## Format JSON des questions

> **Règle** : ce format est la source de vérité pour l'import. Toute modification de `_validate_common()` dans `question_types.py` doit être reflétée ici **et** dans `sample_questions.json`.

### Champs communs à tous les types (obligatoires)

| Champ JSON | Type | Valeurs autorisées | Colonne DB |
|---|---|---|---|
| `type` | string | `multiple_choice`, `true_false`, `multiple_opinions_dropdown` | `question_type` |
| `parcours` | string | `"bassar_bechalav"` (liste dans `VALID_PARCOURS`) | `parcours` |
| `sujet` | string | texte hébreu non vide — thème traité **dans le siman** (peut couvrir plusieurs seifim ; sert au regroupement des cartes dans le sélecteur). Résolu vers un [`Subject`](#subjects) stable par correspondance exacte `(parcours, siman, texte)` — texte déjà vu ⇒ réutilisé, sinon nouveau sujet créé | `subject_id` (via `subjects.get_or_create_subject()`) |
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
  "sujet": "משך ההמתנה בין בשר לחלב",
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
  "sujet": "איסור חלב מיד לאחר בשר",
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
  "sujet": "דין תבשיל שטעמו בשר לענין ההמתנה",
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
Règles : ≥ 2 decisors, chaque `correct_choice` doit être dans `dropdown_choices`, et au moins deux `correct_choice` distincts (désaccord réel obligatoire).

---

## Générer des questions JSON avec une IA

> Cette section s'adresse à quiconque veut utiliser un LLM pour produire des questions en masse.  
> **Règle** : l'IA doit lire la section [Format JSON des questions](#format-json-des-questions) ci-dessus avant de générer quoi que ce soit — les contraintes y sont définitives.

### Prompt de référence

Le prompt complet et à jour vit dans **[`prompt_generation_questions.md`](prompt_generation_questions.md)**
(racine du repo). Il encode, en plus du format JSON ci-dessus :

- le workflow obligatoire en 5 passes (lecture du texte source → génération → re-vérification
  contre le texte → audit des réponses/distracteurs → relecture linguistique hébreu) avant
  toute sortie JSON ;
- la politique de choix des types : machloket réelle entre poskim → `multiple_opinions_dropdown`,
  type par défaut → `multiple_choice`, `true_false` réservé aux cas vraiment binaires ;
- les règles pédagogiques (atomicité, anti-interférence, qualité des distracteurs, sources
  citées dans `explanation`).

Dans Claude Code, la commande **`/generate-cards`** (`.claude/commands/generate-cards.md`)
applique ce prompt et valide le lot généré avec `question_types.normalize_imported_question()`
avant livraison.

### Exemple de lot JSON valide

```json
[
  {
    "type": "multiple_choice",
    "parcours": "bassar_bechalav",
    "sujet": "משך ההמתנה בין בשר לחלב",
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
    "sujet": "איסור חלב מיד לאחר בשר",
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
    "sujet": "דין תבשיל שטעמו בשר לענין ההמתנה",
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
- **Statut initial** : toute question importée arrive avec `status="pending"` — elle n'est visible que par un `validator`/`super_admin` dans `/admin/questions` jusqu'à approbation explicite (voir [règle de statut](#règle-métier--file-dattente-par-défaut-et-signalement)).

---

## Routes et API

### Authentification (`/`)

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Landing page |
| GET/POST | `/auth` | Login ou signup étudiant (formulaire double mode, sélecteur d'onglets כניסה/הרשמה) — `?mode=signup` ouvre directement l'onglet inscription |
| GET | `/logout` | Déconnexion |

---

### Espace étudiant (`/app/*`) — `@login_required`

| Méthode | Route | Description |
|---|---|---|
| GET | `/app/` | Redirige vers onboarding ou home |
| GET/POST | `/app/onboarding` | Choix des **parcours** (multi-select, ≥ 1 requis), date de מבחן **par parcours** (optionnelle), niveau cible, sections |
| GET | `/app/home` | Dashboard : salutation + message contextuel (examen imminent ≤ 7 j > cartes dues > série active > défaut), streak, puis **une section par parcours activé** (compte à rebours du מבחן du parcours, barre de préparation, stats rapides — précision/nb réponses/cartes dues — et **deux tuiles d'action carrées côte à côte** « המשך הלמידה » / « חזרה יומית » scopées à ce parcours) |
| GET | `/app/parcours` | Table des matières : **un seul parcours affiché à la fois** (sélectionné par `?p=<code>`, défaut = premier parcours activé) → simanim rétractables → cartes par sujet (plage de seifim indicative). Avec ≥ 2 parcours activés, un sélecteur en tête de page (icône de bascule + menu) permet de changer de parcours ; un code inconnu retombe sur le premier |
| GET | `/app/chapitre/<subject_id>[/<seif>]` | Session d'étude sur un sujet (le siman est implicite via `subject_id`) — restreinte aux parcours activés (la variante `/<seif>` reste supportée mais n'est plus liée depuis le sélecteur) |
| GET | `/app/revision` | Hub de révision : 4 cartes (jour / siman / sujet / aléatoire) avec compteurs (parcours activés uniquement) |
| GET | `/app/revision/jour` | Révision du jour : session directe si ≤ 1 parcours actif, sinon **écran de choix du parcours** (compteur de cartes dues par parcours + option « הכל ») |
| GET | `/app/revision/jour/<parcours>` | Session de révision du jour restreinte à un parcours actif ; valeur spéciale `all` = tous les parcours actifs. Parcours inconnu/non activé → redirection vers le sélecteur |
| GET | `/app/revision/siman` | Liste des simanim déjà appris (parcours → siman → cartes par sujet) |
| GET | `/app/revision/siman/<subject_id>` | Session de révision sur un sujet déjà appris d'un siman |
| GET | `/app/revision/sujet` | Liste des tags (`Question.tags`) ayant ≥ 3 cartes déjà apprises |
| GET | `/app/revision/sujet/<tag>` | Session de révision sur toutes les cartes déjà apprises portant ce tag |
| GET | `/app/revision/aleatoire` | Session de révision aléatoire (max 10 cartes déjà apprises, retirée à chaque visite) |
| POST | `/app/advance-revisions` | Avance toutes les cartes dues de 1 jour (outil de test) |
| POST | `/app/reset-progress` | Efface UserAnswer + FsrsCard + Progression (nucléaire) |
| GET | `/app/profil` | Profil — tableau de bord statistique type Anki. **Le bloc analytique n'apparaît qu'à partir de `STATS_MIN_CARDS` (30) cartes apprises** ; en dessous, une jauge de progression « הסטטיסטיקות בדרך » (X/30) remplace précision, maturité, mémoire, prévision, heatmap et récap (les KPIs points/série/cartes restent visibles). Une fois débloqué : précision globale, KPIs (points, série courante, **série record**, cartes apprises), **maturité des cartes** (répartition par état FSRS `בשליטה`/`בלמידה`/`חזרה מחדש`/`חדש`), zone mémoire & activité (עוצמת זיכרון ממוצעת = stabilité moyenne, חזרות השבוע, ממתינים היום/השבוע, נושאים שהושלמו, ימי לימוד), **תחזית חזרות** (graphe « Future Due » : cartes à réviser par jour à venir + courbe cumulée, sélecteur 7 / 30 / toute la période — données via `_revision_forecast()`, rendu SVG vanilla côté client), **יומן פעילות** (heatmap 12 semaines), récap par parcours (cartes/précision/réponses/dus) et bloc יעדים ומבחנים (target_stability + date de מבחן par parcours). Stats calculées par `_profile_stats()` |
| GET/POST | `/app/settings` | Activer/désactiver les parcours et leur date de מבחן (≥ 1 parcours requis ; désactiver = masquer le contenu + perdre la série quotidienne du parcours), target_stability, sections |
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
| GET | `/admin/validate` | Redirection héritée vers `/admin/questions?status=pending` (l'onglet unifié) |
| POST | `/admin/validate/approve-all` | Approuve en un clic toutes les questions `pending` (bouton « אשר הכל » de `/admin/questions` filtré sur `pending`) |
| GET | `/admin/questions` | Recherche/édition de toutes les questions — filtres `status`, `type`, `parcours`, `siman`, `q` (texte libre) |
| POST | `/admin/questions/<qid>/edit` | Sauvegarde / approuve / signale à revoir / rejette une question depuis `/admin/questions` (actions `save` / `approve` / `flag` / `reject` — `flag` et `reject` exigent une note) — résout aussi les `QuestionReport` "open" de la question (`"dismissed"` sur sauvegarde/approbation, `"confirmed"` sur rejet) |
| GET | `/admin/reports` | File des signalements personnels `QuestionReport.status="open"` — carte non retirée pour tout le monde, juste pour le(s) signaleur(s) |
| POST | `/admin/reports/<report_id>/confirm` | Signalement jugé justifié — retire la question pour tout le monde (`Question.status="pending"`, rejoint `/admin/questions`) et classe tous les signalements "open" de la question en `"confirmed"` |
| POST | `/admin/reports/<report_id>/dismiss` | Signalement jugé injustifié — classe ce signalement en `"dismissed"`, la question redevient visible pour ce seul étudiant |
| POST | `/admin/subjects/rename` | Renomme le titre d'un [`Subject`](#subjects) par ID (une seule ligne modifiée), depuis `/admin/dashboard` (bloc « שאלות לפי נושא ») — si le nouveau titre entre en collision avec un autre sujet du même siman, fusionne les deux (questions + `Progression` réassignées, ancien sujet supprimé) |
| POST | `/admin/reset-db` | **super_admin uniquement** — réinitialise les données tout en restaurant le compte propriétaire protégé avec le même ID/mot de passe/rôle (confirmation texte `"RESET"` requise) |

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

> **`combo` n'est qu'un indice d'affichage** — le serveur **ne lui fait pas confiance**. Le combo
> autoritaire (celui qui sert de multiplicateur de points) est **recalculé côté serveur** à partir
> de l'historique réel de l'utilisateur (voir [Système de points](#système-de-points-pointspy)).
> La réponse renvoie le `combo` recalculé, que le client resynchronise pour l'affichage.

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

`daily_bonus` — bonus de complétion quotidienne **par parcours** (150 + 20 par jour de série
consécutive de CE parcours). Toujours `0` sauf quand `mode == "revision_daily"` **et** que cette
réponse vide complètement la file des cartes dues du jour **du parcours de la question**
(`FsrsCard.due_date <= aujourd'hui`, questions approuvées, signalements "open" de l'utilisateur
exclus) — auquel cas il est ajouté à `total_points` en plus de `points`. En mode « הכל », chaque
parcours dont la file se vide déclenche son propre bonus, cumulables le même jour (garde
`last_daily_completion_date` par parcours). `daily_bonus_parcours` (libellé hébreu du parcours,
`null` sinon) accompagne le bonus pour l'affichage.

**Effets de bord** (dans l'ordre) :
1. Enregistre un `UserAnswer` (avec `z_item`, `z_user`, `auto_grade`, `predicted_r`)
2. Crée ou met à jour la `FsrsCard` (scheduling FSRS-6, prior collectif par item si carte neuve)
3. Met à jour la calibration collective : Elo (`ItemStats.elo_difficulty`, `StudentProfile.elo_ability`),
   compteurs et distributions log-RT (`ItemStats`, `UserSpeed`)
4. Met à jour (ou crée) la `Progression` du chapitre
5. Met à jour `StudentProfile` : `total_points`, `streak_days`, `last_activity_date`
6. Si `mode == "revision_daily"` et que la file du jour **du parcours de la question** vient d'être
   vidée : ajoute le bonus de complétion quotidienne (`daily_bonus`) à `total_points` et met à jour
   `daily_completion_streak` / `last_daily_completion_date` **sur la ligne `student_parcours`** du
   parcours (plus jamais sur `StudentProfile`)

#### `POST /api/report`

Signalement d'une question, depuis le bouton 🚩 du lecteur (`chapitre.js`). Le comportement dépend
du rôle de l'utilisateur qui signale (voir [règle de signalement](#règle-métier--file-dattente-par-défaut-et-signalement)) :

- **Étudiant simple** (aucun rôle staff) : crée un `QuestionReport` (`status="open"`) — la question
  n'est retirée **que pour lui**, `Question.status` global n'est pas touché.
- **`validator` / `super_admin`** : retrait immédiat pour tout le monde — `Question.status` passe
  à `"a_revoir"` et une `QuestionEdit` (`action="reported"`, `note=reason`) est journalisée.

Corps JSON attendu :
```json
{
  "question_id": "uuid",
  "reason": "motif optionnel du signalement"
}
```

Réponse JSON : `{"ok": true}`.

---

### Webhook de déploiement (`/webhook/*`)

| Méthode | Route | Description |
|---|---|---|
| POST | `/webhook/deploy` | Récepteur de webhook GitHub — `git pull --ff-only origin main` sur push vers `main`, puis reload PythonAnywhere optionnel (voir [Déploiement continu](#déploiement-continu-pythonanywhere)) |

---

## Logique métier clé

### Algorithme FSRS-6 (`fsrs.py`)

Port maison de l'algorithme publié **FSRS-6** (21 poids `w0–w20`, valeurs par défaut vérifiées
contre `py-fsrs`), sans dépendance externe. La courbe d'oubli est personnalisable via `w20`
(`DECAY = −w20`), la difficulté utilise le *linear damping* + réversion à la moyenne vers `D0(Easy)`,
et un lapse ne peut jamais augmenter la stabilité (cap FSRS-6).

- **Rating automatique** (pas de choix utilisateur) : déduit de l'exactitude + de la vitesse
  **personnelle** de l'étudiant sur cette carte précise (`fsrs.personal_bucket`), pas d'un
  z-score collectif ni de seuils absolus par difficulté.
  - Rating 1 = mauvais, 2 = lent (≥ 1/3 plus lent que la référence), 3 = moyen (référence
    inchangée), 4 = rapide (≤ 1/3 plus rapide que la référence).
  - La « référence » est le temps de réponse du **premier succès** sur la carte tant que FSRS
    n'a pas encore été engagé, puis la moyenne glissante des 3 derniers temps
    (`FsrsCard.avg_response_time_ms`) une fois engagé — voir *Cycle de vie d'une carte* ci-dessous.
  - La calibration collective par z-score (`calibration.bucket_from_z`, seuils absolus
    `fsrs.speed_bucket`/`THRESHOLDS`) continue de tourner en arrière-plan (Elo, `ItemStats`,
    priors S0/D0 des nouvelles cartes) mais ne pilote plus ni ce rating ni le bonus de points —
    voir *Calibration collective* plus bas.

#### Cycle de vie d'une carte : activation avant scheduling

Le tout premier passage sur une carte ne déclenche **aucun calcul FSRS**. La carte n'est
réellement planifiée par l'algorithme qu'à partir du premier succès qui suit un cycle
d'activation :

1. **Jamais réussie** — tant que l'étudiant n'a jamais répondu juste à cette carte, un échec ne
   crée ni ne modifie aucune `FsrsCard` : 0 point, aucune planification. La carte reste
   librement accessible depuis `/app/parcours` et réapparaît dans la session de lecture en
   cours (`queue.push(q)` dans `chapitre.js`).
2. **Premier succès (activation)** — la `FsrsCard` est créée, planifiée pour le lendemain
   (`due_date = aujourd'hui + 1 jour`), **sans** calcul de stabilité/difficulté. L'étudiant
   gagne systématiquement `FIRST_CONTACT_POINTS` (20) points, et le temps de réponse est
   retenu comme référence (`avg_response_time_ms`).
3. **Passage suivant** — si l'étudiant répond juste, FSRS s'engage enfin : le rating est dérivé
   de `personal_bucket(référence, temps_de_réponse)` et `schedule_next` tourne pour la première
   fois (prior collectif par item éventuellement injecté, comme pour toute carte `state="new"`).
   S'il répond faux, la carte est simplement replanifiée au lendemain (0 point, référence
   inchangée) et ce cycle se répète jusqu'au premier succès.
4. **Cartes engagées** — une fois `schedule_next` exécuté au moins une fois, le rating de
   chaque révision suivante compare le temps de réponse à la moyenne glissante
   `avg_response_time_ms` (mise à jour via `fsrs.roll_avg`), avec la même règle ±1/3.
- **Rétentabilité** : `R(t, S) = (1 + FACTOR × t / S)^DECAY`, avec `DECAY = −w20`.
- **Intervalle optimal** : `interval = S / FACTOR × (target^(1/DECAY) − 1)` (≈ `S × 0.40` à `target = 0.95`).
- **Pression examen** : compression continue quand l'examen est à moins de 90 jours.
  - Facteur `max(0.30, days_left / 90)` — linéaire ; plafond absolu : l'intervalle ne dépasse jamais `days_left`.
  - La date d'examen utilisée est celle du **parcours de la question** (`student_parcours.exam_date`,
    résolue dans `blueprints/api.py`) — chaque parcours a sa propre pression ; un parcours sans date
    n'en subit aucune.
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
- **`soften_first_contact`** — conservée dans `fsrs.py` (couverte par `tests/test_fsrs.py`) mais
  n'est plus appelée par `blueprints/api.py` : la toute première exposition à une carte ne passe
  plus du tout par `rating_for` (voir *Cycle de vie d'une carte* ci-dessus), donc ce garde-fou
  n'a plus lieu d'être sur le chemin réel.

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

### Instrumentation de la rétention

Sans mesure de rétention réelle, tout réglage FSRS (`CAP_FIRST`, `WARMUP_INTERVALS`, `W7_FLOOR`,
priors Elo) reste une conjecture invérifiable. Le système journalise donc, pour chaque révision
d'une carte déjà engagée, le **R prédit** (`UserAnswer.predicted_r`, calculé sur l'état de la carte
*avant* mise à jour via `fsrs.retrievability`) à côté du résultat réel (`is_correct`).

- **Métriques** (`calibration.retention_report`) sur les paires `(predicted_r, is_correct)` :
  - **log loss** (primaire — la cross-entropie binaire réellement optimisée par FSRS) ;
  - **RMSE(bins)** (lisible — « en moyenne on se trompe de X en prédisant R ») ;
  - **true retention** (taux de rappel observé) vs **rétention prédite** (moyenne des `predicted_r`).
- **Restitution** : `scripts/recompute_item_stats.py` imprime le rollup global + par parcours ;
  `/admin/dashboard` affiche un bloc « כיול ושימור » (shomer/kiyul) calculé en direct depuis le
  journal append-only. Repère de décision : un écart *true vs predicted* > ~5 points d'% signale
  des réglages ou des poids à revoir.

### Système de points (`points.py`)

Trois formules distinctes selon le `mode` transmis à `POST /api/answer` (voir
[POST /api/answer](#post-apianswer)) — **aucun multiplicateur de streak** : le seul mécanisme lié à
la régularité est le bonus de complétion quotidienne explicite (`daily_bonus`, calculé dans
`blueprints/api.py`, pas dans `points.py`), pour éviter un double comptage.

Dans les trois formules : mauvaise réponse → 0 point, combo réinitialisé à 0.
`combo` (multiplicateur commun) : `{2: ×1.1, 3: ×1.2, 4: ×1.3, 5+: ×1.5}`.

> **Combo autoritaire côté serveur (anti-triche).** Le combo qui sert de multiplicateur n'est
> **jamais** pris depuis le corps de la requête — le `combo` du client est purement décoratif.
> `blueprints/api.py` le recalcule à partir de la dernière réponse de l'utilisateur : le combo
> monte d'un cran sur chaque bonne réponse **consécutive**, et repart à 0 sur une mauvaise réponse
> ou après un trou de plus de `COMBO_SESSION_GAP` (30 min, garde de session). Sans ça, un client
> modifié pourrait gonfler ses points **et** polluer les signaux de latence (`z_item`) / d'Elo en
> récompensant la vitesse/volume bruts.

> **Cas particulier — cycle d'activation d'une carte** : tant qu'une carte n'a jamais été
> engagée par FSRS (voir *Cycle de vie d'une carte* dans la section FSRS-6 ci-dessus), ces
> formules ne s'appliquent pas : le premier succès rapporte `FIRST_CONTACT_POINTS` (20 points
> fixes) et tout échec avant ce premier succès (ou avant l'engagement FSRS qui suit) rapporte
> 0 point. Ce cas est géré directement dans `blueprints/api.py`, pas dans `points.py`.

#### `compute_points` — étude normale (`mode` omis ou `"study"`)

```
points = (base + bonus_difficulté + bonus_vitesse) × multiplicateur_combo

base = 10
bonus_difficulté : {1: +2, 2: +4, 3: +6}
bonus_vitesse    : {rapide: +5, moyen: +2, lent: 0}
```

`bonus_vitesse` est dérivé de `fsrs.personal_bucket` — comparaison au propre temps de
référence de l'étudiant sur cette carte (±1/3), pas d'un z-score collectif.

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

`normalize_imported_question()` valide et normalise les 3 types à l'import :

| Type | Règles spécifiques |
|---|---|
| `multiple_choice` | ≥ 2 options numérotées en séquence (1, 2, 3, …), une ou plusieurs bonnes réponses (plusieurs = sélection multiple) |
| `true_false` | Booléen simple |
| `multiple_opinions_dropdown` | ≥ 2 "decisors" (opinions), choix parmi liste, désaccord réel obligatoire |

Valide aussi les **champs communs obligatoires** : `parcours` (valeur dans `VALID_PARCOURS`), `sujet` (texte hébreu non vide), `siman` (entier > 0), `seif` (entier > 0), `difficulty_level` (1, 2 ou 3).

### Filtre Jinja2 `to_hebrew` (`app.py`)

Convertit un entier en notation hébraïque (gematria) avec geresh/gershayim :
- `1` → `א׳`, `10` → `י׳`, `89` → `פ״ט`
- Cas spéciaux : 15 → `ט״ו`, 16 → `ט״ז` (évite les combinaisons יה / יו)
- Utilisé dans les templates : `{{ s.siman | to_hebrew }}`, `{{ sf.seif | to_hebrew }}`

### Page Parcours (`/app/parcours`)

- **Un seul parcours affiché à la fois.** Le parcours actif est choisi par le paramètre
  `?p=<code>` (défaut : le premier parcours activé, ordre alphabétique). Un code inconnu ou non
  activé retombe silencieusement sur le premier.
- **Sélecteur de parcours** (visible uniquement quand ≥ 2 parcours sont activés) : en tête de page,
  une pastille affiche le libellé du parcours courant + une icône de bascule ; l'ouvrir déroule un
  menu (pur HTML/CSS via `<details>`, sans JS) listant tous les parcours activés — chaque entrée est
  un lien `?p=<code>` qui recharge la page sur le parcours choisi (coche ✓ sur le parcours courant).
  Avec un seul parcours activé, le sélecteur est remplacé par le simple en-tête `.toc-group-subject`.
- En-tête par **parcours** (ex : `בשר בחלב`, libellé dans `PARCOURS_LABELS` de `question_types.py`)
- Chaque **siman** est un `<details>` rétractable avec son numéro en hébreu (פ״ט, צ׳, …) et son titre (édité dans `/admin/topics`, indexé par parcours dans `siman_seif_topics.json`)
- À l'intérieur : **cartes par sujet** — les questions sont groupées par `Question.subject_id` (voir [`subjects`](#subjects)), le titre affiché est `Subject.title` — cliquables avec indicateur ✓ si complété, compteur de questions et plage indicative des seifim couverts (ex : `א–ג`)
- Cliquer une carte ouvre une session sur toutes les questions du sujet (`/app/chapitre/<subject_id>`)
- Aucun siman n'est verrouillé — l'étudiant accède librement à n'importe quel sujet

### Multi-parcours

Un étudiant peut préparer **plusieurs parcours en parallèle**, chacun avec sa propre date de מבחן :

- **Activation** : à l'onboarding (multi-select, ≥ 1 requis) et dans les paramètres. Une ligne
  `student_parcours` = un parcours actif. Désactiver un parcours **supprime la ligne** (date +
  série quotidienne perdues) ; les `fsrs_cards` restent en base et réapparaissent à la réactivation
  (attention au backlog de cartes dues accumulées).
- **Filtre de contenu global** : un parcours non activé est masqué **partout** — `/app/parcours`,
  `/app/home`, `/app/chapitre/…` (y compris accès URL directe) et toutes les révisions. Implémenté
  par `Question.parcours.in_(codes actifs)` via les helpers `get_active_parcours()` /
  `active_parcours_codes()` (`blueprints/student.py`).
- **Révision du jour** : avec plusieurs parcours actifs, `/app/revision/jour` affiche d'abord un
  écran de choix (compteur de cartes dues par parcours + « הכל ») ; la session est ensuite scoppée
  au parcours choisi (`/app/revision/jour/<parcours>` ou `/all`).
- **Bonus quotidien par parcours** : vider la file due d'un parcours déclenche SON bonus
  (150 + 20×série du parcours) ; en mode « הכל » les bonus des différents parcours se cumulent le
  même jour.
- **Pression FSRS par parcours** : `schedule_next` reçoit la date du parcours de la question.
- **Ajouter un parcours au catalogue** = 3 entrées dans `question_types.py` : `VALID_PARCOURS`,
  `PARCOURS_LABELS`, `PARCOURS_DESCRIPTIONS` — onboarding, paramètres et sélecteur de révision se
  mettent à jour automatiquement.
- **Parcours multi-chelek (`chupa_kidushin`)** : premier parcours à couvrir des simanim de
  **deux chalakim différents** du Choulhan Aroukh (Even haEzer ET 'Hochen Mishpat). Le champ
  `siman` (Integer) ne porte aucune notion de chelek, donc les numéros de siman peuvent se
  chevaucher entre les deux parties. **Solution provisoire** (à adapter structurellement plus
  tard — voir CLAUDE.md, section « Parcours multi-chelek ») : chaque question précise son chelek
  via un préfixe dans `source_ref` — `ehy` pour אבן העזר, `chum` pour חושן משפט (ex.
  `"ehy סי' כו סע' א"`). Les fichiers de lot générés suivent la même convention :
  `generated_questions_ehy_<siman>.json` / `generated_questions_chum_<siman>.json`.
- **Base existante** : `python -m scripts.migrate_multi_parcours` crée la table et rattache chaque
  profil onboardé à `bassar_bechalav` en copiant les champs dépréciés (le fallback de
  `get_active_parcours()` fait de même à la volée si besoin).

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

### Règle métier : file d'attente par défaut et signalement

Toute question importée arrive par défaut en **`"pending"`** (en attente) — elle n'est visible que dans `/admin/questions` (accès `validator`/`super_admin`), jamais aux étudiants. 4 états possibles pour `Question.status` :

| Statut | Visible par les étudiants ? | Comment y arriver |
|---|---|---|
| `pending` | Non | Défaut à l'import (`POST /admin/import` action `import`) |
| `approved` | Oui | Le validateur/admin approuve depuis `/admin/questions` (action `approve`) ou en masse (`POST /admin/validate/approve-all` sur le filtre `pending`) |
| `a_revoir` | Non | Le validateur/admin signale une question déjà approuvée comme à corriger (bouton 🚩 « סמן לבדיקה » sur `/admin/questions`, action `flag` — note obligatoire), ou un signalement étudiant est confirmé justifié, ou un `validator`/`super_admin` signale directement une question depuis le lecteur (`POST /api/report`) |
| `rejected` | Non | Le validateur/admin rejette depuis `/admin/questions` (action `reject`, note obligatoire) — décision finale, atteignable depuis `pending` ou `a_revoir` |

Le signalement d'une question (bouton 🚩 dans `chapitre.js`, `POST /api/report`) a un effet différent selon le rôle de qui signale :

- **Étudiant simple** (aucun rôle staff) — la question est retirée **uniquement pour lui** : un `QuestionReport` (`status="open"`) est créé, `Question.status` global n'est pas modifié et les autres étudiants continuent de voir la question normalement. Toutes les requêtes du parcours étudiant (`blueprints/student.py`, helper `_hidden_question_ids()`) excluent les questions ayant un `QuestionReport` "open" pour l'utilisateur courant. La question réapparaît pour lui dès qu'un validateur tranche :
  - **Confirme** (`POST /admin/reports/<id>/confirm`) → retrait pour **tout le monde** : `Question.status="a_revoir"`, la carte rejoint la file "לתיקון" de `/admin/questions` pour correction/rejet, et le signalement passe à `"confirmed"`.
  - **Rejette** (`POST /admin/reports/<id>/dismiss`) → le signalement était injustifié : passe à `"dismissed"`, la question redevient visible pour ce seul étudiant.
  - **Modifie/ré-approuve la question** depuis `/admin/questions` (`POST /admin/questions/<qid>/edit`, action `save`/`approve`) → résout aussi automatiquement tout `QuestionReport` "open" de cette question en `"dismissed"` (elle a été corrigée, redevient visible pour ceux qui l'avaient signalée). Un rejet (`action="reject"`) les classe en `"confirmed"`.
- **`validator` / `super_admin`** — retrait immédiat **pour tout le monde** : `Question.status` passe à `"a_revoir"` et une `QuestionEdit` (`action="reported"`, `note`=motif) est journalisée. La question disparaît du parcours de tous les étudiants jusqu'à décision dans `/admin/questions`.
- **Signalement interne depuis `/admin/questions`** (action `flag`, note obligatoire) — même effet que ci-dessus mais déclenché directement par le validateur/admin en train d'éditer la carte (`QuestionEdit` `action="flagged"`), sans passer par le lecteur étudiant.
- **File d'attente des signalements personnels** — `/admin/reports` (accès staff) liste tous les `QuestionReport` "open", avec boutons "אשר" (confirmer, retrait global) / "דחה" (rejeter le signalement).
- **Base existante** — `scripts/migrate_requeue_approved.py` rebascule en `pending` les questions `approved` d'une base existante, pour aligner les anciennes données sur ce nouveau défaut (⚠️ rend tout le contenu déjà approuvé invisible aux étudiants jusqu'à revalidation — à lancer délibérément, pas automatiquement). La table `question_reports` est créée automatiquement par `db.create_all()` (nouvelle table, pas de script de migration nécessaire).

---

## Pipeline d'import des questions

```
Importer (JSON) → Prévisualisation (normalize_imported_question) → Sauvegarde status="pending"
                                                                          ↓
                                                    (invisible aux étudiants — visible en /admin/questions)
                                                                          ↓
                                          /admin/questions → édite / approuve / rejette
                                                                          ↓
                                      Approuve → status="approved" (visible de tous)
                                                                          ↓
                              ┌─────────────────────────┴─────────────────────────┐
                              ↓                                                     ↓
            Étudiant simple signale (🚩)                          validator/super_admin signale (🚩 lecteur ou "סמן לבדיקה")
            → QuestionReport "open"                                → status="a_revoir" (retrait global)
            (retrait pour lui SEUL)                                            ↓
                              ↓                                    /admin/questions (filtre "לתיקון") → édite/approuve/rejette
              /admin/reports (file des signalements)
                    ↓                        ↓
      confirme (justifié)          rejette (injustifié)
      → status="a_revoir"          → QuestionReport "dismissed"
        (retrait global,             (redevient visible pour
         rejoint /admin/questions)    ce seul étudiant)
                              ↓
            /admin/questions → édite (→ reports "dismissed") / approuve / rejette (→ reports "confirmed")
                                    ↓                        ↓
                              Approuve → status="approved"   Rejette → status="rejected" + note
                                    ↓
              Audit enregistré dans question_edits (action="approved"/"flagged"/"rejected"/"reported")
```

Le format JSON d'import accepte un tableau d'objets. Chaque objet est normalisé par `question_types.py`. Les erreurs de validation sont remontées ligne par ligne dans la prévisualisation — aucune question n'est importée si le lot contient des erreurs.

---

## Rôles et authentification

**Mécanisme** : session Flask (`session["user_id"]`) + chargement dans `g.user` avant chaque requête via `@app.before_request`.

**Rester connecté** : la case « הישאר מחובר » du formulaire `/auth` (`remember`) est transmise à
`login_user(user, remember=...)` (`auth_helpers.py`), qui positionne `session.permanent`. Décochée
(défaut) → cookie de session, effacé à la fermeture du navigateur. Cochée → cookie persistant, durée
`PERMANENT_SESSION_LIFETIME` (`config.py`, 30 jours par défaut).

**Restriction temporaire de l'inscription** : `/auth` en mode `signup` (`blueprints/auth.py`)
n'autorise la création de compte que pour les emails listés dans `ALLOWED_SIGNUP_EMAILS`
(`config.py`, liste blanche séparée par des virgules ; vide/non défini = seul `SUPER_ADMIN_EMAIL`
peut s'inscrire). Toute autre adresse reçoit un message d'erreur (« ההרשמה סגורה כרגע ») sans créer
de compte. Cette restriction ne s'applique pas aux comptes créés par `seed.py` (appelle
`create_account()` directement, en dehors du formulaire).

| Rôle | Accès | Attribution |
|---|---|---|
| `student` | `/app/*` — signaler une question (🚩) ne la retire que pour lui-même (`QuestionReport`) | Par défaut à l'inscription |
| `importer` | `/admin/*` + import JSON | Manuel (super_admin) |
| `validator` | `/admin/*` + validation + `/admin/reports` (confirmer/rejeter les signalements) — voit aussi les questions `pending` dans `/app/parcours` et peut les ouvrir dans le lecteur ; signaler une question (🚩) la retire immédiatement pour **tout le monde** | Manuel (super_admin) |
| `super_admin` | Tout + reset DB — voit aussi les questions `pending` dans `/app/parcours` et dispose des mêmes privilèges de signalement que `validator` | Permanent pour `bcbeneghmos@gmail.com`; auto aussi si email = `SUPER_ADMIN_EMAIL`, sinon manuel |

### Administration, sauvegardes et accès d’urgence

- `/admin/questions` est la source principale de modification, validation et analyse des questions. Les écrans de signalements et de suggestions y renvoient, sans dupliquer l’éditeur.
- Depuis le lecteur, un `validator` envoie une **suggestion** : elle ne modifie jamais la question. Un `super_admin` peut ouvrir directement l’éditeur de cette question.
- La tâche `python -m scripts.run_backup` crée une sauvegarde cohérente et conserve les sept dernières sauvegardes ordinaires. Une sauvegarde marquée à conserver dans `/admin/backups` reste présente jusqu’à sa suppression manuelle. Voir `docs/pythonanywhere_backups.md` pour la tâche PythonAnywhere de minuit.
- L’API SQL d’urgence est désactivée sans `EMERGENCY_SQL_API_ENABLED=1`. Elle exige un jeton éphémère créé par un super-admin, une requête HMAC horodatée (60 secondes) et inscrit chaque tentative dans l’audit. Elle est réservée aux incidents : une requête SQL arbitraire confère par nature des droits complets sur les données.

Décorateurs disponibles dans `auth_helpers.py` :
- `@login_required` — redirige vers `/auth` si non connecté
- `@staff_required` — redirige vers `/admin/denied` si pas de rôle staff

Un utilisateur peut avoir plusieurs rôles simultanément (table `user_roles`).
Le rôle `super_admin` du compte propriétaire protégé ne peut être retiré ni par lui-même,
ni par un autre super-admin, ni par une écriture SQL directe sur la base SQLite.

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
python -m scripts.migrate_approve_pending  # (historique) approuve les questions "pending" — ancien défaut
python -m scripts.migrate_requeue_approved  # rebascule les questions "approved" en "pending" — nouveau défaut (base EXISTANTE)
python -m scripts.migrate_multi_parcours   # crée student_parcours + backfill (base EXISTANTE)

# Tests (sans pytest requis)
python tests/test_fsrs.py
python tests/test_calibration.py
python tests/test_points.py
python tests/test_multi_parcours.py
python tests/test_protected_admin.py
python tests/test_pending_parcours_visibility.py

# Vérifier l'état de la base en SQLite
sqlite3 smiha.db ".tables"
sqlite3 smiha.db "SELECT email, role FROM users JOIN user_roles ON users.id=user_roles.user_id;"

# Variables d'env pour la prod (Bash)
export SECRET_KEY="..." DATABASE_URL="postgresql+psycopg://..." SUPER_ADMIN_EMAIL="..."
python app.py

# Synchroniser la base locale avec la base de prod (PythonAnywhere)
# Nécessite PA_USERNAME + PA_API_TOKEN (Account > API Token sur pythonanywhere.com)
# PA_DB_PATH optionnel si le chemin diffère de /home/<PA_USERNAME>/smiha-flask/smiha.db
# Ces variables peuvent être mises dans un fichier .env à la racine (chargé automatiquement,
# non commit — voir .gitignore) plutôt que exportées manuellement.
export PA_USERNAME="..." PA_API_TOKEN="..."          # Bash
$env:PA_USERNAME="..."; $env:PA_API_TOKEN="..."      # PowerShell
python -m scripts.sync_prod_db && python app.py

# Synchronisation automatique au démarrage (flask run / python app.py)
# Ajouter AUTO_SYNC_DB=1 dans le .env (avec PA_USERNAME/PA_API_TOKEN) : app.py appelle
# alors scripts/sync_prod_db.py avant de servir. Désactivé par défaut (opt-in) pour ne
# jamais déclencher de téléchargement en prod.

# Git — sauvegarder les credentials GitHub une seule fois (ex. sur PythonAnywhere)
git config --global credential.helper store
```

#### Note — colonnes additives appliquées au démarrage

`db.create_all()` crée les tables manquantes mais n'ajoute jamais de colonne à une
table déjà existante : historiquement, chaque colonne ajoutée à un modèle (`z_item`,
`z_user`, `auto_grade`, `elo_ability`, `predicted_r`) nécessitait de lancer à la main
le script `migrate_*.py` correspondant sur la base de prod après déploiement — une
étape facile à oublier (cause vécue d'un `/admin/dashboard` et d'un `POST /api/answer`
qui plantaient silencieusement après un déploiement, faute de migration). `app.py`
(`_ensure_additive_columns`, appelé dans `create_app()` juste après `db.create_all()`)
applique désormais ces `ALTER TABLE ADD COLUMN` automatiquement à chaque démarrage,
de façon idempotente (sans effet si la colonne existe déjà). Les scripts
`migrate_phase2` / `migrate_predicted_r` restent utilisables pour appliquer le
correctif sans redémarrer le process. Ne couvre que les colonnes purement additives
(`ADDITIVE_COLUMNS` dans `app.py`) — les migrations de données (`migrate_approve_pending`,
`migrate_multi_parcours`) restent des scripts à lancer manuellement, une seule fois.

---

## Service worker & mise à jour automatique

L'app sert un service worker (`GET /sw.js`, route Flask — pas un fichier statique) pour éviter
qu'un navigateur affiche une version obsolète des assets `static/` après un déploiement.

- **Versioning** : `APP_VERSION` est calculé une seule fois au démarrage (`app.py`), via
  `git rev-parse --short HEAD` ; fallback sur un timestamp si `.git` est absent. Il est injecté dans
  `templates/sw.js.jinja` comme `CACHE_NAME = "smiha-static-{APP_VERSION}"`. Le nom du cache change
  donc à chaque déploiement, ce qui fait changer les octets de `/sw.js` et déclenche la détection
  native de mise à jour du navigateur.
- **`/sw.js` est une route Flask** (pas un fichier dans `static/`) car son contenu dépend de
  `APP_VERSION`, calculé au runtime — un fichier statique ne pourrait pas être régénéré à chaque
  déploiement sans étape de build. La réponse est servie avec
  `Cache-Control: no-cache, must-revalidate` pour que le fichier lui-même ne soit jamais mis en
  cache par le navigateur (sinon la détection de mise à jour serait retardée).
- **Portée** : le service worker n'intercepte que les requêtes `GET /static/*`
  (stale-while-revalidate). Toute autre requête (pages HTML, `/app/*`, `/admin/*`, `/auth/*`,
  `/api/*`) passe en direct — aucune donnée dynamique/authentifiée n'est mise en cache.
- **Bandeau de mise à jour** : script inline dans `templates/base.html` — enregistre le SW, affiche
  un bandeau (« גרסה חדשה זמינה ») quand une nouvelle version est installée en arrière-plan, et
  recharge la page une fois l'utilisateur cliqué « רענן ».
- **Manifest PWA** : `static/manifest.json`, icônes `static/images/icon-192.png` / `icon-512.png`
  générées depuis `static/favicon.svg` via `scripts/generate_pwa_icons.py` (à relancer manuellement
  si le favicon change — nécessite `cairosvg`, non listé dans `requirements.txt` car outil de build
  uniquement, pas une dépendance runtime).
- **Règle** : ne jamais committer/hardcoder un nom de cache statique — tout est dérivé
  automatiquement de `APP_VERSION`.

---

## Déploiement continu (PythonAnywhere)

PythonAnywhere (plan gratuit) n'autorise pas de processus persistant en dehors du serveur WSGI de
l'app — impossible d'y faire tourner un service webhook séparé. `blueprints/webhook.py` fait donc
servir le webhook GitHub par l'app Flask elle-même (déjà toujours active) : `POST /webhook/deploy`
exécute `git pull --ff-only origin main` dans le dossier du dépôt à chaque push sur `main`.

### 1. Générer un secret et le configurer côté serveur

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Sur PythonAnywhere, onglet **Web** → **Environment variables** (ou dans le fichier WSGI avant
`from app import app`) :

```bash
export GITHUB_WEBHOOK_SECRET="le-secret-généré-ci-dessus"
```

### 2. Autoriser `git pull` sans mot de passe interactif

```bash
git config --global credential.helper store
git pull origin main   # une fois manuellement, pour enregistrer les credentials
```

### 3. Créer le webhook côté GitHub

Dans le dépôt GitHub → **Settings** → **Webhooks** → **Add webhook** :

| Champ | Valeur |
|---|---|
| Payload URL | `https://<votre-username>.pythonanywhere.com/webhook/deploy` |
| Content type | `application/json` |
| Secret | le même secret que `GITHUB_WEBHOOK_SECRET` |
| Événements | `Just the push event` |

GitHub envoie un événement `ping` immédiatement après la création — `/webhook/deploy` y répond
`{"ok": true, "message": "pong"}` (200) sans toucher au dépôt, ce qui permet de vérifier la
connectivité sans attendre un vrai push.

### 4. (Optionnel) Recharger automatiquement le web app après le `pull`

Sur PythonAnywhere, un `git pull` seul ne suffit pas : le process WSGI doit être rechargé pour
servir le nouveau code. `_reload_pythonanywhere()` (`blueprints/webhook.py`) essaie deux mécanismes,
dans cet ordre :

1. **`touch` du fichier WSGI** (`/var/www/<domain-avec-underscores>_wsgi.py`) — PythonAnywhere
   recharge automatiquement une webapp dès que ce fichier est modifié. Fonctionne sur **tous les
   plans, y compris gratuit** ; seul `PYTHONANYWHERE_USERNAME` (et éventuellement
   `PYTHONANYWHERE_DOMAIN` si différent de `<username>.pythonanywhere.com`) est requis.
2. **Fallback API** — si le `touch` échoue (chemin WSGI non standard, environnement non
   PythonAnywhere…) et que `PYTHONANYWHERE_API_TOKEN` est renseigné, appelle
   `POST /api/v0/user/<username>/webapps/<domain>/reload/`. **Attention** : cet endpoint répond
   `403 "You do not have permission to perform this action"` sur les comptes gratuits (Beginner) —
   réservé aux plans payants. Ne pas s'y fier comme seul mécanisme sur un compte gratuit.

Sans `PYTHONANYWHERE_USERNAME` du tout, le reload est ignoré (`reloaded: false`) et il faut cliquer
sur **Reload** dans l'onglet **Web** après chaque déploiement.

### Vérification

La réponse JSON de `/webhook/deploy` (visible dans l'onglet **Recent Deliveries** du webhook
GitHub) indique `pull_output`, `reloaded` et `reload_message` — utile pour diagnostiquer un échec
sans avoir besoin d'une console PythonAnywhere.

> **Sécurité** : la route vérifie la signature `X-Hub-Signature-256` (HMAC-SHA256 du corps de la
> requête avec `GITHUB_WEBHOOK_SECRET`) avant toute action ; sans secret configuré ou avec une
> signature invalide, aucune requête ne peut déclencher de `git pull`. Seuls les push vers
> `refs/heads/main` déclenchent un pull — tout autre event/branche est ignoré (`200`, no-op).

---

## Points d'attention pour un futur développeur

- **RTL** : tous les templates ont `lang="he" dir="rtl"`. Ajouter du HTML sans tester en hébreu peut casser l'alignement.
- **`section` est une liste JSON** sur `StudentProfile` et `Question`. Utiliser `question.section_list()` pour la lire de façon cohérente.
- **Filtrage strict des sections** : une question n'est proposée que si **toutes** ses sections sont dans celles de l'étudiant (`question.sections ⊆ student.sections`). Exemple : une question `["shulchan_aruch", "tur"]` est invisible pour un étudiant qui n'a que `shulchan_aruch`. Pas d'alias, pas d'implicite (sauf `shulchan_aruch` toujours injecté par `allowed_sections()`).
- **Champs obligatoires des questions** : `parcours`, `sujet`/`subject`, `siman`, `seif` sont requis depuis l'import. Modifier leur validation dans `question_types.py` **doit** s'accompagner d'une mise à jour de ce README et de `sample_questions.json`.
- **`VALID_PARCOURS`** dans `question_types.py` est la liste des parcours autorisés. Ajouter un parcours = ajouter ici + `PARCOURS_LABELS` + `PARCOURS_DESCRIPTIONS` + mettre à jour ce README.
- **`chupa_kidushin`** est un parcours multi-chelek (Even haEzer + 'Hochen Mishpat, préfixes `ehy`/`chum` dans `source_ref`, faute de colonne `chelek` dédiée) — voir CLAUDE.md avant d'y ajouter du contenu ou de retoucher `question_types.py`/le pipeline d'import le concernant.
- **Filtrage par parcours actifs** : tout le parcours étudiant filtre sur `Question.parcours.in_(parcours actifs)`. Une question avec `parcours = NULL` est **invisible** pour tous les étudiants (la migration `migrate_multi_parcours` log un warning si de telles questions existent).
- **Parcours désactivé** : ses cartes dues s'accumulent invisiblement ; à la réactivation l'étudiant retrouve tout le backlog d'un coup (le compteur du sélecteur de révision le rend explicite).
- **Tests** : le cœur SRS est couvert par `tests/test_fsrs.py` et `tests/test_calibration.py`
  (runner autonome, pytest optionnel) ; le reste de l'app n'a pas de couverture — vérifier les
  régressions manuellement et étendre les tests avant d'ajouter une feature complexe.
- **FSRS-6 — réglages produit** : `CAP_FIRST`, `WARMUP_INTERVALS`, `W7_FLOOR`, `ALPHA_MAX` s'écartent
  volontairement des défauts FSRS. Ils doivent être **validés empiriquement** sur les logs réels
  (rétention cible vs réelle), pas figés. `scripts/sim_schedule.py` sert à les balayer.
- **Calibration collective** : les priors par item ne remplacent jamais FSRS à 100 % (mélange
  plafonné à `ALPHA_MAX`). L'Elo est mis à jour en ligne ; `scripts/recompute_item_stats.py` est la
  source autoritaire des μ/σ de latence — le lancer en batch (cron nocturne) pour la stabilité.
- **Migration** : les colonnes Phase 2 sont désormais ajoutées automatiquement au démarrage sur
  une base existante (voir [note sur les migrations additives](#note--colonnes-additives-appliquées-au-démarrage)) ;
  `python -m scripts.migrate_phase2` reste disponible pour les appliquer sans redémarrer le process.
  Une base neuve (`python seed.py`) est déjà au bon schéma.
- **File d'attente par défaut** : `Question.status` vaut `"pending"` par défaut, avec 4 états
  possibles — `pending` / `approved` / `a_revoir` / `rejected` (voir
  [règle métier](#règle-métier--file-dattente-par-défaut-et-signalement)). Sur une base existante
  déjà passée par l'ancien défaut `"approved"`, lancer `python -m scripts.migrate_requeue_approved`
  pour rebasculer les questions `approved` en `pending` (⚠️ les retire temporairement de la vue
  étudiant jusqu'à revalidation).
- **Prévisualisation du parcours par les validateurs** : `/app/parcours` et `/app/chapitre/*`
  incluent `pending` pour les rôles `validator` et `super_admin`, mais continuent d'exiger
  `approved` pour les étudiants ordinaires. `POST /api/answer` applique la même autorisation
  afin qu'un étudiant ne puisse pas répondre à une question `pending` en connaissant son ID.
- **`FsrsCard.target_stability`** est copié depuis `StudentProfile` à la création de la carte. Modifier le profil étudiant ne met pas à jour les cartes existantes — prévu par design.
- **`/app/reset-progress`** efface `UserAnswer`, `FsrsCard`, `Progression` sans confirmation supplémentaire. Protéger en prod si nécessaire.
- **`/admin/reset-db`** réinitialise les données et déconnecte l'utilisateur, mais restaure immédiatement le compte propriétaire `bcbeneghmos@gmail.com` avec le même ID, mot de passe et rôle `super_admin`. Réservé au `super_admin`, requiert la saisie du mot `"RESET"` en confirmation.
- **`seed.py`** insère les comptes de démo avec des mots de passe en clair dans le code. Ne pas utiliser en prod.
- **`chapitre.js`** gère l'état du combo côté client et l'envoie avec chaque réponse. Le serveur fait confiance à cette valeur — un client malveillant pourrait l'altérer.
