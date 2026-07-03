# Design — Navigateur de questions admin (`/admin/questions`)

**Date :** 2026-07-03  
**Statut :** approuvé  

---

## Contexte

Le back-office admin actuel expose `/admin/validate` pour réviser les questions en attente, mais :

- Les champs `tags` et `source_ref` ne sont pas éditables dans l'UI
- Il n'existe pas de vue pour naviguer ou modifier des questions déjà approuvées ou rejetées
- Aucune recherche/filtre avancé n'est disponible

## Objectif

Créer une page `/admin/questions` — navigateur complet + éditeur JSON — permettant de consulter et modifier n'importe quelle question, quel que soit son statut.

---

## Architecture

### Layout

Deux panneaux côte à côte (identique à `/admin/validate`) :

- **Sidebar gauche** : liste scrollable des questions filtrées
- **Panneau droit** : éditeur complet de la question sélectionnée

### Filtres (query params)

| Paramètre | Valeurs | Défaut |
|---|---|---|
| `status` | `pending`, `approved`, `rejected`, `` (tous) | `` (tous) |
| `type` | `multiple_choice`, `true_false`, `multiple_opinions_dropdown`, `` | `` |
| `parcours` | `bassar_bechalav`, `` | `` |
| `q` | texte libre (recherche sur subject + question text) | `` |
| `id` | UUID question sélectionnée | premier résultat |

---

## Champs de l'éditeur

### Métadonnées (grille)

| Champ | Widget | Obligatoire |
|---|---|---|
| `parcours` | select (`bassar_bechalav`) | oui |
| `subject` | input texte | oui |
| `siman` | input number | oui |
| `seif` | input number | oui |
| `difficulty` | select 1/2/3 | oui |
| `section` | multi-select (shulchan_aruch, tur, psikei_admur, ptei_teshuva) | oui |
| `tags` | input texte (valeurs séparées par virgules) | non |
| `source_ref` | input texte | non |
| `hint` | textarea | non |

### Contenu (selon `question_type`)

**`multiple_choice`**
- `question_text` — textarea
- 4 options : numéro (readonly) + texte + radio "bonne réponse"

**`true_false`**
- `statement_text` — textarea
- `correct_answer` — select vrai/faux

**`multiple_opinions_dropdown`**
- `question_text` — textarea
- `dropdown_choices` — liste dynamique (ajouter/supprimer)
- `decisors` — liste dynamique (id + nom + correct_choice)

### Bas du formulaire

- `explanation` — textarea
- Note validateur — textarea (obligatoire uniquement pour "Rejeter")

### Boutons d'action

| Bouton | Comportement |
|---|---|
| **Enregistrer** | Sauvegarde tous les champs, conserve le statut actuel |
| **Approuver** | Sauvegarde + passe `status = "approved"` |
| **Rejeter** | Sauvegarde + passe `status = "rejected"` (note obligatoire) |

---

## Routes

### `GET /admin/questions`

Requiert `@staff_required`.  
Récupère les questions selon les filtres, passe au template :

```python
questions       # liste filtrée (order_by created_at desc)
selected        # question active (id via ?id= ou premier résultat)
question_types  # ['multiple_choice', 'true_false', 'multiple_opinions_dropdown']
type_label      # {'multiple_choice': 'רב-ברירה', ...}
filters         # dict des filtres actifs (pour pré-remplir les selects)
```

### `POST /admin/questions/<id>/edit`

Requiert `@staff_required`.  
Lit `action` depuis le form (`save` / `approve` / `reject`).  
Réutilise `_payload_from_form()` et `sync_question_row_from_payload()` existants.  
Enregistre un `QuestionEdit` pour audit.  
Redirige vers `GET /admin/questions?id=<id>&...filtres...`.

---

## Dashboard

Ajout d'un bouton **📋 Toutes les questions** dans la carte "פעולות מהירות" du dashboard, pointant vers `/admin/questions`.

---

## Contraintes respectées

- Types valides : `multiple_choice`, `true_false`, `multiple_opinions_dropdown` uniquement (`practical_scenario` supprimé)
- `shulchan_aruch` toujours inclus dans `VALID_SECTIONS`
- RTL hébreu : aucun nouveau CSS — on réutilise les classes existantes (`card`, `grid`, `stack-sm`, `row`, `badge`, etc.)
- Aucune dépendance externe ajoutée
- Tout audit de modification passe par `QuestionEdit`
