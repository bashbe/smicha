# Redesign Frontend — Smiha Path

**Date :** 2026-07-02  
**Portée :** Refonte visuelle complète de toutes les pages étudiants + landing + auth. Aucune modification de la logique métier, des routes, ni du backend.

---

## 1. Système de base

### Palette — double mode (light / dark)

| Token CSS | Light | Dark |
|---|---|---|
| `--bg` | `#FAFAF9` | `#0F0F0F` |
| `--surface` | `#FFFFFF` | `#1A1A1A` |
| `--fg` | `#111111` | `#EFEFEF` |
| `--muted` | `#888888` | `#555555` |
| `--accent` | `#2563EB` | `#3B82F6` |
| `--border` | `#E5E5E5` | `#2A2A2A` |
| `--success` | `#16A34A` | `#22C55E` |
| `--danger` | `#DC2626` | `#EF4444` |

Le basculement light/dark s'effectue via un attribut `data-theme="dark"` sur `<html>`. Pas de JS framework — une règle `[data-theme="dark"]` redéfinit les tokens.

### Typographie

- **Display :** `Secular One` (titres, chiffres-clés)
- **Corps :** `Noto Sans Hebrew` (tout le reste)
- **Tailles (3 seulement) :** `sm` = 13px · `base` = 16px · `lg` = 20px
- Direction : `dir="rtl"` sur `<html>`, conservé intégralement

### Espacement

Grille de 8px. Valeurs autorisées : 8, 16, 24, 32, 48px. Aucune valeur intermédiaire.

### Border-radius

- Cartes : `12px`
- Boutons : `8px`
- Pills / badges : `9999px`

---

## 2. Layout

### Mobile (prioritaire — breakpoint < 640px)

- Bottom nav fixe, 4 icônes sans label, icône active en `--accent`
- La bottom nav disparaît sur les écrans d'étude (`chapitre`, `revision`) et d'onboarding
- Une seule colonne, scroll vertical, `padding: 16px`

### Desktop (≥ 640px)

- Sidebar fixe à gauche, `200px`, même 4 liens avec labels
- Contenu centré dans une colonne `max-width: 640px`
- Rien à droite de la colonne de contenu

---

## 3. Composants réutilisables

### Bouton primaire
Fond `--accent`, texte blanc, radius `8px`, hauteur `48px` sur mobile. Pleine largeur dans les formulaires et les écrans d'étude.

### Bouton ghost
Bordure `--border`, fond transparent, même dimensions. Utilisé pour les actions secondaires.

### Bloc de choix (opt-card)
Surface `--surface`, bordure `--border` `1px`, radius `12px`, padding `16px`. Quand sélectionné : bordure `--accent` `2px`. Hauteur minimale `56px`, tappable sur toute la surface.

### Barre de progression
Hauteur `4px`, fond `--border`, remplissage `--accent`. Aucun label numérique à côté — le pourcentage se lit visuellement.

### Badge / pill
Fond `--accent` opacité 15%, texte `--accent`, radius `9999px`, padding `4px 10px`, taille `sm`.

---

## 4. Écrans — détail

### Landing (`/`)

```
[Logo / nom de l'app]
[Tagline — 1 ligne]
[Bouton "התחל ללמוד" — pleine largeur]
───────────────────────────────
523 שאלות · FSRS · ∞ חזרות
```

Fond `--bg`. Aucune illustration, aucun hero, aucune section supplémentaire. Le lien admin est un texte discret en `--muted` sous le bouton principal.

---

### Auth (`/auth`)

Formulaire centré, max-width `360px`. Toggle texte "יש לך כבר חשבון? התחבר" pour basculer login ↔ signup. Aucun champ superflu — email + mot de passe (+ nom complet en mode signup).

---

### Onboarding (`/app/onboarding`) — 5 étapes

Header fixe : compteur `X מתוך 5` en `Secular One` + 5 points indicateurs. Nav masquée.

| Étape | Contenu |
|---|---|
| 1 | Choix du sujet — blocs opt-card (בשר בחלב actif, autres grisés avec cadenas) |
| 2 | Date d'examen — calendrier hébraïque existant dans une surface `--surface` |
| 3 | Niveau de maîtrise — 3 opt-cards : 80% · 90% · 99% |
| 4 | Sources — שולחן ערוך verrouillé + 3 checkboxes optionnelles |
| 5 | Confirmation — check `✓` en `--accent`, résumé en `--muted`, bouton "התחל ללמוד" |

Bouton "המשך" verrouillé (grisé, non cliquable) jusqu'à sélection valide. Un seul bouton par étape.

---

### Home (`/app/home`)

```
[Prénom]                    [🔥 X] [● X pts]
● ● ● ● ● ● ●  7 ימים אחרונים
────────────────────────────────
        X ימים עד המבחן
        [════════════    ] barre fine
────────────────────────────────
[  המשך הלמידה — btn primaire  ]
[  חזרה יומית — btn ghost + badge X  ]
```

Aucune carte décorative. Les stats (streak, points) sont sur une ligne de header, pas dans des widgets séparés.

---

### Parcours (`/app/parcours`)

Header discret : `בשר בחלב` en taille `sm`, couleur `--muted`.

Ensuite : liste de simanim. Chaque siman = une ligne accordéon :

```
סימן פ״ט  [══════════     ] ▸
```

Ouvert :
```
סימן פ״ט  [══════════     ] ▾
  └─ סעיף א׳ - ד׳  —  המתנה בין בשר לחלב
  └─ סעיף ה׳        —  גבינה קשה
  └─ סעיף ו׳ - ח׳  —  עוף בחלב
```

Règle de groupement des seifim : les seifim consécutifs portant le même sujet sont fusionnés en une ligne `סעיף X - Y — נושא`. Un seif isolé : `סעיף X — נושא`. Chaque ligne est cliquable.

---

### Chapitre (`/app/chapitre/<subject>/<siman>`) & Révision (`/app/revision`)

Nav masquée. Header fixe :
```
[← retour]   סימן פ״ט · סעיף א׳   [X/N]
[══════════════════════     ]  barre progression
```

**Zone de question** (occupe la majorité de l'écran) :
Texte de la question en `lg`, centré verticalement dans la zone disponible.

**Zone de réponse** (bas de l'écran, fixe) — varie selon le type :

#### `multiple_choice`
4 blocs opt-card empilés, pleine largeur. Après sélection : correct → bordure `--success`, fond `--success` 10% · incorrect → bordure `--danger`, fond `--danger` 10%. Explication apparaît sous les choix. Bouton "הבא" apparaît.

#### `true_false`
2 blocs côte à côte, pleine largeur chacun : `אמת` · `שקר`. Mêmes états après réponse.

#### `multiple_opinions_dropdown`
Liste de déciseurs. Chaque ligne :
```
[השולחן ערוך]   [צריך להמתין]  [אין צריך להמתין]
```
Les deux pills sont tappables, une seule sélectionnable par ligne. Validation globale une fois tous les déciseurs remplis → bouton "הבא" apparaît.

**Règle commune :** le bouton "הבא" n'est jamais visible avant que l'étudiant ait répondu.

---

### Profil (`/app/profil`)

4 stats empilées (valeur en `Secular One` grande, label en `sm` `--muted`) :
- Total réponses
- Précision %
- Streak jours
- Points totaux

Lien "הגדרות" en bas, style ghost.

---

### Settings (`/app/settings`)

Formulaire simple : date d'examen + target_stability + sections. Même composants que l'onboarding. Bouton "שמור" primaire en bas.

---

## 5. Ce que l'IA NE doit PAS faire

- Ajouter des illustrations, icônes décoratives, gradients, ou ombres portées
- Inventer des sections ou widgets non listés ici
- Modifier les routes, les noms de variables Jinja2, les `url_for()`, ou toute logique Python
- Utiliser un framework CSS externe (Tailwind, Bootstrap, etc.)
- Créer des fichiers JS nouveaux — le JS existant (`chapitre.js`, `hebrew-calendar.js`) reste intact
- Modifier les templates admin

---

## 6. Contraintes techniques

- Templates Jinja2 SSR, RTL, `lang="he" dir="rtl"`
- CSS pur dans `static/css/styles.css` — remplacer intégralement
- Vanilla JS uniquement — ne pas toucher `chapitre.js` ni `hebrew-calendar.js`
- Conserver tous les noms de classes CSS référencés dans le JS existant (`hidden`, `step`, `opt-card`, `opt-stability`, `opt-section`, `input-checkbox-auto`, `accent-dot`, `dot`)
- Conserver tous les `data-*` attributs utilisés par le JS existant
