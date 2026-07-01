# Prompt — Génération interface frontend Smiha Path

---

## Contexte

Tu travailles sur **Smiha Path**, une application web de préparation à l'examen de Smikhah (ordination rabbinique). L'app est en hébreu, direction RTL (`dir="rtl"` sur `<html>`), servie en SSR via Flask + Jinja2.

**Stack technique :**
- Templates Jinja2 dans `templates/`
- CSS unique dans `static/css/styles.css` (à réécrire intégralement)
- Vanilla JS dans `static/js/chapitre.js` et `static/js/hebrew-calendar.js` — **ne pas toucher**
- Aucun framework CSS externe (pas de Tailwind, pas de Bootstrap)

**Ta mission : réécrire uniquement la partie visuelle.**
- Réécrire `static/css/styles.css` intégralement
- Modifier les templates HTML listés ci-dessous pour appliquer les nouvelles classes
- Ne modifier aucune logique Jinja2, aucun `url_for()`, aucune variable de contexte, aucun fichier Python
- Ne pas toucher aux templates admin (`templates/admin/`)

---

## Système de design

### Tokens CSS (déclarer dans `:root` et `[data-theme="dark"]`)

```css
:root {
  --bg:      #FAFAF9;
  --surface: #FFFFFF;
  --fg:      #111111;
  --muted:   #888888;
  --accent:  #2563EB;
  --border:  #E5E5E5;
  --success: #16A34A;
  --danger:  #DC2626;
}

[data-theme="dark"] {
  --bg:      #0F0F0F;
  --surface: #1A1A1A;
  --fg:      #EFEFEF;
  --muted:   #555555;
  --accent:  #3B82F6;
  --border:  #2A2A2A;
  --success: #22C55E;
  --danger:  #EF4444;
}
```

Le basculement light/dark se fait en ajoutant `data-theme="dark"` sur `<html>`. Ajouter un bouton toggle discret (icône lune/soleil) dans le header ou la nav — il ajoute/retire l'attribut via JS inline.

### Typographie

- Display : `Secular One` (Google Fonts, déjà chargée)
- Corps : `Noto Sans Hebrew` (Google Fonts, déjà chargée)
- Tailles : `--text-sm: 13px` · `--text-base: 16px` · `--text-lg: 20px`
- `h1, h2, h3` utilisent `Secular One`, `font-weight: 400`

### Espacement

Grille 8px stricte. Valeurs autorisées : `8px, 16px, 24px, 32px, 48px`.

### Border-radius

- Cartes et surfaces : `12px`
- Boutons : `8px`
- Pills / badges : `9999px`

### Règle cardinale

**Un seul appel à l'action principal visible par écran.** Pas de décoration, pas d'ombres portées, pas d'illustrations, pas d'icônes purement décoratives.

---

## Composants réutilisables

### `.btn-primary`
- Fond `--accent`, texte blanc, radius `8px`, hauteur `48px`, pleine largeur dans les formulaires
- État disabled : opacité `0.4`, `cursor: not-allowed`

### `.btn-ghost`
- Bordure `1px solid --border`, fond transparent, mêmes dimensions que `.btn-primary`

### `.opt-card`
- Surface `--surface`, bordure `1px solid --border`, radius `12px`, padding `16px`
- Hauteur minimale `56px`, `cursor: pointer`, tappable sur toute la surface
- Sélectionné : `border: 2px solid --accent`
- Conserver les classes existantes `.opt-card`, `.opt-stability`, `.opt-section` — le JS en dépend

### `.progress-bar`
- Hauteur `4px`, fond `--border`, remplissage `--accent`, radius `9999px`

### `.badge`
- Fond `--accent` à 15% d'opacité, texte `--accent`, radius `9999px`, padding `4px 10px`, taille `--text-sm`

### `.dot` et `.accent-dot`
- Cercle `8px` de diamètre
- `.dot` : fond `--border`
- `.accent-dot` : fond `--accent`
- **Conserver ces classes exactement** — utilisées par `chapitre.js`

---

## Contraintes JS critiques

Les classes et attributs suivants sont référencés par le JS existant. **Ne pas les renommer ni les supprimer :**

| Classe / attribut | Fichier JS | Usage |
|---|---|---|
| `.hidden` | `chapitre.js` | Masquer/afficher des éléments |
| `.step` + `data-step` | `chapitre.js` / onboarding | Navigation entre étapes |
| `.opt-card` | `chapitre.js` | Sélection de choix |
| `.opt-stability` | onboarding inline | Sélection niveau |
| `.opt-section` | onboarding inline | Sélection sources |
| `.input-checkbox-auto` | onboarding inline | Checkboxes sources |
| `.accent-dot`, `.dot` | `chapitre.js` | Indicateurs de progression |
| `data-dot` | onboarding inline | Points de progression |
| `data-next` | onboarding inline | Boutons de navigation |
| `#step-number` | onboarding inline | Affichage numéro étape |
| `#next1` … `#next4` | onboarding inline | Boutons étapes |
| `#cal-root` | `hebrew-calendar.js` | Calendrier hébraïque |
| `#exam_date` | onboarding inline | Input date cachée |
| `#subject-cards`, `#card-bbc` | onboarding inline | Sélection sujet |

---

## Écrans à redesigner

### 1. `templates/base.html`

Layout de base. Ajouter `data-theme` sur `<html>` (vide par défaut = light). Charger `styles.css`. Ne pas modifier la structure des `{% block %}`.

---

### 2. `templates/landing.html`

Page d'accueil non connectée.

**Structure (colonne unique, centrée verticalement) :**
```
[Nom de l'app en Secular One, grande taille]
[Tagline courte en --muted]
[Bouton "התחל ללמוד" — .btn-primary pleine largeur, max 360px]
[Lien "כניסת מנהל →" en --muted, text-sm, centré]
────────────────────────────────────────────
[523 שאלות]  |  [FSRS]  |  [∞ חזרות]
  [label]        [label]     [label]
```

Fond `--bg`. Aucun autre élément.

---

### 3. `templates/auth.html`

Formulaire login / signup.

**Structure (colonne, max-width 360px, centré) :**
- Titre de la page (`h2`)
- Champs : email + mot de passe (+ nom complet si mode signup)
- Bouton submit `.btn-primary`
- Texte toggle mode en bas : `"יש לך כבר חשבון? התחבר"` — lien texte `--accent`

Conserver le mécanisme existant de double mode (le formulaire gère login/signup via un champ caché ou une variable Jinja).

---

### 4. `templates/student/_layout.html`

Layout partagé de toutes les pages étudiant.

**Mobile :** bottom nav fixe en bas, hauteur `60px`, fond `--surface`, bordure haute `1px solid --border`. 4 liens : icônes uniquement, pas de labels. Icône active : couleur `--accent`, les autres `--muted`.

**Desktop (≥ 640px) :** sidebar fixe à gauche, `200px`, fond `--surface`, bordure droite `1px solid --border`. Même 4 liens avec labels texte. Contenu dans une colonne `max-width: 640px`, centrée.

Ajouter le toggle light/dark dans la nav (icône lune/soleil).

La bottom nav est masquée quand `show_nav` est `false` (déjà géré par la variable Jinja `{% if show_nav | default(true) %}`).

---

### 5. `templates/student/onboarding.html`

Formulaire 5 étapes séquentiel. Nav masquée (`show_nav = false`).

**Header fixe :**
```
[1]  מתוך 5        ● ● ○ ○ ○
```
Chiffre en `Secular One` `--accent`. Points : 5 `.dot`, l'actif et les précédents en `.accent-dot`.

**Étape 1 — Sujet :** blocs `.opt-card` pour chaque sujet. Sujet actif (בשר בחלב) normal. Autres : opacité `0.4`, `cursor: not-allowed`, icône cadenas.

**Étape 2 — Date :** surface `--surface` radius `12px` contenant `#cal-root`. Le calendrier hébraïque est généré par `hebrew-calendar.js` — ne pas y toucher.

**Étape 3 — Niveau :** 3 blocs `.opt-card.opt-stability`. Chaque bloc : pourcentage en `Secular One` grande taille (`--muted` par défaut, `--accent` si sélectionné) + titre + description.

**Étape 4 — Sources :** שולחן ערוך en `.opt-card` verrouillé (opacité `0.75`, icône cadenas). 3 `.opt-card.opt-section` avec checkbox `.input-checkbox-auto`.

**Étape 5 — Confirmation :** `✓` en `Secular One` grand, `--accent`. Texte résumé en `--muted`. Bouton submit `.btn-primary`.

Chaque étape : bouton `.btn-primary` en bas, disabled jusqu'à sélection valide (géré par le JS inline existant — ne pas modifier).

---

### 6. `templates/student/home.html`

**Structure (`.stack`, padding `16px`) :**

```
[Avatar initiale]  [Prénom]        [🔥 X]  [● X pts]
● ● ● ● ● ● ●   7 ימים אחרונים

──────────────────────────────────
        [X]  ימים עד המבחן        ← Secular One, grande
        [══════════════     ]      ← .progress-bar

──────────────────────────────────
[      המשך הלמידה      ]         ← .btn-primary
[  חזרה יומית  [badge X] ]        ← .btn-ghost + .badge si due_count > 0
```

Pas de cartes séparées pour les stats. Tout est texte et layout.

---

### 7. `templates/student/parcours.html`

**Header discret :** nom du sujet en `--text-sm` `--muted` (ex : `בשר בחלב`).

**Liste de simanim — accordéon :**

Chaque siman = une ligne cliquable :
```
סימן פ״ט    [══════     ]    ▸
```
- Numéro en hébreu (géré par le filtre Jinja `| to_hebrew`)
- Barre de complétion `.progress-bar` fine, à droite
- Chevron ▸ / ▾ indiquant état ouvert/fermé
- Fond `--bg`, séparé des autres par une ligne `--border`

Ouvert :
```
סימן פ״ט    [══════     ]    ▾
  └─ סעיף א׳ - ד׳  —  המתנה בין בשר לחלב     ✓
  └─ סעיף ה׳        —  גבינה קשה
  └─ סעיף ו׳ - ח׳  —  עוף בחלב
```

Chaque ligne de seifim :
- Indentée de `24px`
- Format : `סעיף X — נושא` (seif unique) ou `סעיף X - Y — נושא` (plage)
- Si complété : `✓` en `--success` à droite
- Cliquable sur toute la ligne → `url_for('student.chapitre', ...)`
- Fond `--surface` sur les lignes de seifim (contraste doux avec le fond `--bg` du siman)

La logique de groupement des seifim par sujet et de génération des plages est déjà dans le template Jinja existant — ne pas la modifier, adapter seulement le HTML de rendu.

---

### 8. `templates/student/chapitre.html` & `templates/student/revision.html`

Nav masquée. Structure identique pour les deux écrans.

**Header fixe :**
```
[← retour]    סימן פ״ט · סעיף א׳    [X / N]
[══════════════════════════     ]   ← .progress-bar
```

**Zone question** (scroll si besoin) :
- Texte de la question en `--text-lg`, `Noto Sans Hebrew`
- Padding `24px`

**Zone de réponse** (fixe en bas, fond `--surface`, bordure haute `1px solid --border`) :

#### Type `multiple_choice` et `practical_scenario`
4 blocs `.opt-card` empilés, pleine largeur, padding `16px`.

États après réponse :
- Correct : `border: 2px solid --success`, fond `--success` à 10%
- Incorrect sélectionné : `border: 2px solid --danger`, fond `--danger` à 10%
- Correct non sélectionné (révélation) : `border: 2px solid --success`

Explication apparaît sous les choix en `--text-sm` `--muted`. Bouton `.btn-primary` "הבא" apparaît.

#### Type `true_false`
2 blocs `.opt-card` côte à côte, pleine largeur (`flex`, `gap: 8px`) :
- `אמת` (Vrai) à droite (RTL)
- `שקר` (Faux) à gauche

Mêmes états après réponse que ci-dessus.

#### Type `multiple_opinions_dropdown`
Liste de déciseurs. Chaque ligne :
```
[nom du déciseur]    [option A]  [option B]
```
Les deux options sont des `.opt-card` compactes (pills), une seule sélectionnable par ligne.
Bouton `.btn-primary` "בדוק" apparaît une fois tous les déciseurs remplis.
Après validation : chaque ligne passe en état correct/incorrect.

**Règle commune :** le bouton de navigation "הבא" / "בדוק" est invisible (`display: none`) avant réponse — le JS existant gère cet état via les classes `.hidden`.

---

### 9. `templates/student/profil.html`

4 stats empilées :
```
[Valeur — Secular One, text-lg]
[Label — text-sm, --muted     ]
```
Séparées par une ligne `--border`. Pas de cartes.

Lien `.btn-ghost` "הגדרות" en bas.

---

### 10. `templates/student/settings.html`

Formulaire simple :
- Date d'examen (même composant calendrier que l'onboarding si applicable, sinon `<input type="date">`)
- `target_stability` — 3 blocs `.opt-card.opt-stability` comme l'onboarding étape 3
- Sections — mêmes checkboxes que l'onboarding étape 4
- Bouton `.btn-primary` "שמור" en bas

---

## Ce que tu NE dois PAS faire

- Ajouter des illustrations, gradients, ombres portées, ou images
- Inventer des sections ou widgets non décrits dans ce prompt
- Modifier les variables Jinja2, les `url_for()`, ou les expressions `{% if %}` existantes
- Modifier `chapitre.js` ou `hebrew-calendar.js`
- Utiliser un framework CSS externe
- Modifier les templates dans `templates/admin/`
- Renommer ou supprimer les classes listées dans la section "Contraintes JS critiques"

---

## Ordre de livraison suggéré

1. `static/css/styles.css` — système complet (tokens, reset, utilitaires, composants)
2. `templates/base.html` — layout de base + `data-theme`
3. `templates/student/_layout.html` — nav mobile + sidebar desktop
4. `templates/landing.html`
5. `templates/auth.html`
6. `templates/student/home.html`
7. `templates/student/parcours.html`
8. `templates/student/chapitre.html`
9. `templates/student/revision.html`
10. `templates/student/onboarding.html`
11. `templates/student/profil.html`
12. `templates/student/settings.html`
