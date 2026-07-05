# Design — Modes de révision multiples + refonte du système de points

Date : 2026-07-05

## Contexte

Actuellement `/app/revision` affiche uniquement les cartes FSRS dues aujourd'hui
(tri par stabilité croissante). Ce document ajoute 3 modes de révision
supplémentaires et refond le calcul des points pour éviter les incitations
perverses (ex : échouer volontairement une carte pour la voir réapparaître
plus vite et gagner plus de points).

## 1. Navigation — Hub de révision

`/app/revision` devient une page **hub** avec 4 cartes cliquables (remplace
l'affichage direct des cartes dues) :

| Carte | Route | Contenu |
|---|---|---|
| 📅 Révision du jour | `/app/revision/jour` | Comportement actuel : cartes dues aujourd'hui, triées par stabilité croissante |
| 📖 Par siman/seif | `/app/revision/siman` puis `/app/revision/siman/<subject>/<siman>` | Réutilise l'UI de `/app/parcours` (même structure `<details>` + chips), mais filtrée aux cartes **déjà répondues au moins une fois** (peu importe `due_date`). Titre différent de la page. |
| 🏷️ Par sujet | `/app/revision/sujet` puis `/app/revision/sujet/<subject>` | Liste des sujets ayant **≥ 3 cartes déjà apprises** par l'étudiant. Cliquer sur un sujet lance la session avec toutes ses cartes apprises. |
| 🎲 Aléatoire | `/app/revision/aleatoire` | Lance immédiatement une session de **10 cartes maximum**, tirées aléatoirement parmi les cartes déjà apprises. Resélectionnées à chaque visite (pas de graine fixe). |

Les 3 nouveaux modes ignorent `due_date` — ils portent sur l'ensemble des
cartes pour lesquelles il existe au moins un `UserAnswer` de l'étudiant.

Le lien de nav existant (`_layout.html`, icône חזרה) et le lien depuis
`home.html` pointent tous deux vers `student.revision` → doivent continuer de
fonctionner et mener au hub.

## 2. Système de points — 3 formules distinctes

### 2.1 Principe

Le problème identifié : si les points de révision dépendaient uniquement de
la stabilité FSRS, un étudiant pourrait échouer exprès une carte facile pour
la faire réapparaître avec un intervalle plus court et gagner plus de points
à répétition. La solution retenue sépare deux logiques :

- **Mode "Jour"** (cartes dues, obligatoires) : les points dépendent du temps
  écoulé depuis la dernière réponse, **pas** de la stabilité — échouer une
  carte ne peut pas artificiellement augmenter les points futurs puisque le
  timer redémarre à la date du jour, pas à une date antérieure.
- **Modes "Siman / Sujet / Aléatoire"** (révision volontaire, hors due_date) :
  les points restent liés à la rétrievabilité FSRS (`R`), plafonnés bas (8
  points max) pour limiter l'impact d'un éventuel abus.

### 2.2 Suppression du multiplicateur de streak

Le `streak_multiplier` actuel dans `points.py` (×1.2 à 7+ jours, ×1.5 à 30+
jours de `streak_days`) est **supprimé** de `compute_points()`, pour tous les
modes (étude normale incluse). Il est remplacé par le bonus de complétion
quotidienne explicite (section 3), qui est le seul mécanisme de récompense
lié à la régularité — pour éviter un double comptage.

`streak_days` / `last_activity_date` sur `StudentProfile` restent inchangés
et continuent d'être affichés (flamme sur `/app/home`), mais n'affectent plus
le calcul des points.

Le `combo_multiplier` (×1.1 à ×1.5 selon la série de bonnes réponses
consécutives) continue de s'appliquer dans tous les modes.

### 2.3 Étude normale (hors révision)

Formule inchangée : `(base=10 + bonus_difficulté + bonus_vitesse) × combo_multiplier`,
sans multiplicateur streak (retiré comme ci-dessus). Mauvaise réponse → 0 point.

### 2.4 Révision du jour

```
jours = (aujourd'hui - FsrsCard.last_review.date()).days
base  = min(30, 10 × log10(jours + 1))
total = min(30, round(base × combo_multiplier))
```

- `FsrsCard.last_review` existe toujours pour une carte présentée en
  révision du jour (elle a été créée à la première réponse, `last_review`
  n'est jamais `None` pour ces cartes).
- Le cap final de 30 est réappliqué **après** le multiplicateur de combo,
  pour que ×1.5 ne dépasse jamais l'intention du plafond.
- Mauvaise réponse → 0 point (comportement standard conservé).

### 2.5 Révision Siman / Sujet / Aléatoire

```
R     = retrievability(elapsed_days, stability)   # fsrs.py, déjà existant
elapsed_days = (aujourd'hui - FsrsCard.last_review.date()).days
base  = min(8, round(8 × (1 - R)))
total = min(8, round(base × combo_multiplier))
```

- Réutilise directement `fsrs.retrievability()` — aucune nouvelle constante
  de normalisation introduite (contrairement à une première idée de seuil
  arbitraire "60 jours de stabilité", abandonnée).
- Mauvaise réponse → 0 point.

### 2.6 Sélection de la formule côté API

`POST /api/answer` reçoit un champ `mode` optionnel dans le corps JSON,
envoyé par le front (`chapitre.js`, via `data-points-mode` sur le conteneur
du lecteur) :

| Valeur `mode` | Formule utilisée |
|---|---|
| absent / `"study"` | 2.3 |
| `"revision_daily"` | 2.4 |
| `"revision_siman"` / `"revision_sujet"` / `"revision_random"` | 2.5 |

## 3. Bonus de complétion quotidienne

### 3.1 Nouveaux champs (`StudentProfile`)

| Champ | Type | Description |
|---|---|---|
| `daily_completion_streak` | Integer, défaut 0 | Jours consécutifs où la session "Révision du jour" a été entièrement terminée |
| `last_daily_completion_date` | Date, nullable | Dernière date où le bonus a été attribué |

Distincts de `streak_days`/`last_activity_date` existants (qui restent
purement informatifs, cf. 2.2).

### 3.2 Déclenchement

Après traitement d'une réponse en mode `revision_daily` dans `/api/answer` :

1. Recompter les `FsrsCard` avec `due_date <= today` pour l'utilisateur.
2. Si ce compte est passé à **0** avec cette réponse (i.e. était > 0 juste
   avant, cf. count avant l'upsert de la carte) **et**
   `last_daily_completion_date != today` :
   - `daily_completion_streak = 1` si `last_daily_completion_date` n'est pas
     hier, sinon `daily_completion_streak += 1`
   - `bonus = 150 + 20 × (daily_completion_streak - 1)`
   - `total_points += bonus`
   - `last_daily_completion_date = today`
   - Le bonus est renvoyé dans la réponse JSON (`daily_bonus`) pour affichage
     front (célébration façon `renderRevisionComplete()` déjà existante dans
     `chapitre.js`).

### 3.3 Edge case documenté

Si aucune carte n'est due un jour donné, aucun événement de complétion n'est
enregistré ce jour-là (rien à "terminer"). Si le lendemain des cartes sont à
nouveau dues et complétées, le streak repart à 1 (l'écart avec
`last_daily_completion_date` dépasse 1 jour). Comportement accepté comme cas
limite rare — un étudiant actif a presque toujours des cartes dues.

## 4. Requêtes par mode (backend)

### 4.1 Révision par siman/seif

Réutilise la logique de `parcours()` (`blueprints/student.py:164`) mais :
- Filtre les questions à celles ayant `question.id` dans
  `{q.question_id for UserAnswer where user_id=sp.id}` (peu importe
  `is_correct` — "déjà apprise" = au moins une tentative).
- Template : nouveau `revision_siman_list.html` qui étend la structure de
  `parcours.html` (mêmes classes CSS `toc-*`, `seif-chip`) avec un titre
  différent ("חזרה לפי סימן" au lieu de "תוכן הענינים").
- Clic sur un seif/siman → session de type `_load_chapitre`-like mais sans
  exclure les questions déjà répondues correctement (contrairement à
  `_load_chapitre` qui exclut les bonnes réponses — ici on veut réviser même
  ce qui est déjà correct).

### 4.2 Révision par sujet

- Requête : `subject` groupé, `HAVING COUNT(DISTINCT question_id où user a répondu) >= 3`.
- Nouveau template `revision_sujet_list.html` : liste simple de sujets avec
  compteur de cartes apprises.
- Clic sur un sujet → toutes les cartes apprises de ce sujet.

### 4.3 Révision aléatoire

- Requête : toutes les cartes apprises de l'étudiant, échantillon aléatoire
  de 10 max (`ORDER BY RANDOM() LIMIT 10` en SQLite/Postgres via
  `func.random()` SQLAlchemy), régénéré à chaque visite de la route.

## 5. Modifications de fichiers prévues

| Fichier | Changement |
|---|---|
| `models.py` | + `daily_completion_streak`, `last_daily_completion_date` sur `StudentProfile` |
| `points.py` | Suppression `streak_multiplier` ; + `compute_daily_points()`, `compute_stability_points()` |
| `blueprints/student.py` | Hub `/app/revision` ; nouvelles routes `revision_jour`, `revision_siman`, `revision_siman_detail`, `revision_sujet`, `revision_sujet_detail`, `revision_aleatoire` |
| `blueprints/api.py` | Lecture du champ `mode` ; routage vers la bonne formule ; logique bonus complétion quotidienne |
| `templates/student/revision.html` | Devient le hub (4 cartes) |
| `templates/student/revision_jour.html` | Nouveau (contenu actuel de `revision.html` déplacé ici) |
| `templates/student/revision_siman_list.html` | Nouveau |
| `templates/student/revision_sujet_list.html` | Nouveau |
| `static/js/chapitre.js` | Transmet `mode` dans le payload `/api/answer` ; affiche le bonus quotidien le cas échéant |

## 6. Points de vigilance (README)

- RTL hébreu à vérifier sur les 3 nouveaux templates.
- Migration DB nécessaire pour les 2 nouveaux champs `StudentProfile`
  (pas de système de migration formel dans ce projet — vérifier comment
  `seed.py`/`models.py` gèrent l'évolution du schéma SQLite existant).
- Pas de tests automatisés dans ce projet (rappel README) — vérification
  manuelle requise sur `/app/home`, `/app/revision/*`, `/app/parcours`.
