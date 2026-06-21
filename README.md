# סמיכה — Smiha Path (Flask + SQL)

Réécriture en **Python / Flask / SQLAlchemy** de l'application TanStack Start + Supabase
d'origine. Application RTL hébraïque de préparation à l'examen de Smiha : parcours de
questions, répétition espacée (FSRS), points / combos / séries, et back-office d'import
et de validation des questions.

## Stack

- **Flask** — serveur web + templates Jinja2 (rendu côté serveur, RTL)
- **Flask-SQLAlchemy** — ORM ; **SQLite** par défaut (configurable vers Postgres/MySQL)
- Authentification par session + hachage de mots de passe (Werkzeug) — remplace Supabase Auth
- Logique métier portée 1:1 depuis TypeScript : `fsrs.py`, `points.py`, `question_types.py`

## Installation

```bash
cd smiha-flask
python -m pip install -r requirements.txt
python seed.py        # crée la base + comptes de démo + questions d'exemple
python app.py         # http://localhost:5000
```

### Comptes de démonstration

| Rôle        | Email                     | Mot de passe  |
|-------------|---------------------------|---------------|
| super_admin | bcbeneghmos@gmail.com     | password123   |
| student     | student@example.com       | password123   |

> Comme dans l'app d'origine, l'email `SUPER_ADMIN_EMAIL` (config) est automatiquement
> promu `super_admin` à l'inscription ; tout autre compte devient `student`.

## Configuration (variables d'environnement)

- `DATABASE_URL` — ex. `postgresql+psycopg://user:pw@host/db` (défaut : SQLite local)
- `SECRET_KEY` — clé de session (à changer en production)
- `SUPER_ADMIN_EMAIL` — email auto-promu super_admin

## Structure

```
app.py                 factory Flask + enregistrement des blueprints
config.py              configuration
models.py              modèles SQLAlchemy (schéma issu des migrations Supabase)
auth_helpers.py        session, décorateurs login_required / staff_required
fsrs.py                planificateur de répétition espacée (port de src/lib/fsrs.ts)
points.py              calcul des points/combos (port de src/lib/points.ts)
question_types.py      normalisation/validation des 4 types (port de question-types.ts)
seed.py                données de démarrage
blueprints/
  auth.py              landing, /auth (login/signup étudiant), /logout
  student.py           /app : onboarding, home, parcours, chapitre, profil, revision
  admin.py             /admin : login, dashboard, import, validate
  api.py               /api/answer (enregistrement réponse + FSRS + points + progression)
templates/             Jinja2 (base, student/*, admin/*)
static/css/styles.css  thème sombre navy/indigo/ambre RTL (port de styles.css)
static/js/chapitre.js  lecteur de questions interactif
```

## Modèle de données

Tables (équivalent du schéma Postgres/Supabase final, après les 4 migrations) :
`users` (auth+profil), `user_roles`, `student_profiles`, `questions`, `question_edits`,
`progression`, `user_answers`, `fsrs_cards`.

Les 4 types de questions sont préservés : `multiple_choice`,
`multiple_opinions_dropdown`, `practical_scenario`, `true_false`.

## Différences avec l'original

- L'auth Supabase (JWT + RLS) est remplacée par des sessions Flask ; les règles RLS sont
  appliquées dans le code via les décorateurs et les filtres par `user_id`.
- L'import JSON et la validation se font côté serveur (les 4 formats et toutes les règles
  de validation hébraïques sont conservés).
- Le SPA React est remplacé par des pages rendues côté serveur ; seul le lecteur de
  chapitre reste piloté en JavaScript (`static/js/chapitre.js`) via l'API `/api/answer`.
```
