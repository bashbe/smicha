# Design — Refonte mobile-first (approche C)

**Date :** 2026-07-03  
**Statut :** approuvé

---

## Contexte

L'app Smiha est utilisée par des étudiants (espace `/app/*`) et une équipe de staff (espace `/admin/*`). L'espace étudiant a une fondation mobile déjà présente (bottom-nav responsive, container 40rem, viewport-fit=cover) mais contient des bugs de layout page par page. L'espace admin est entièrement desktop-first et inutilisable sur mobile.

---

## Périmètre

- **Espace étudiant** : audit + corrections ciblées page par page
- **Espace admin** : refonte complète mobile (hamburger nav, onglets two-panel, layout responsive)
- **CSS** : ajouts ciblés dans `styles.css` — pas de réécriture complète

---

## Architecture

### Couche 1 — CSS (`static/css/styles.css`)

Ajouts uniquement, sous `@media (max-width: 768px)` :

```css
/* Admin responsive */
.container-wide { padding: var(--space-2); }
.admin-two-col  { grid-template-columns: 1fr; }
.admin-nav-items { display: none; }
.admin-hamburger { display: flex; }

/* Student fixes */
/* (voir détails par page ci-dessous) */
```

Nouvelle classe CSS `.admin-two-col` remplace les `style="grid-template-columns:320px 1fr"` inline sur `validate.html` et `questions.html`.

### Couche 2 — Nav admin hamburger (`admin/_layout.html`)

**Mobile (< 768px) :**
- Bouton ☰ affiché (`class="admin-hamburger"`)
- Items de nav (`class="admin-nav-items"`) masqués
- Overlay `<div id="nav-drawer">` : plein écran, fond `rgba(0,0,0,0.5)`, panneau qui s'ouvre depuis la droite (RTL), liste verticale des liens
- Pas d'animation — apparition/disparition instantanée
- Fermeture : clic sur le backdrop, clic sur un lien, touche `Escape`
- `padding-bottom: env(safe-area-inset-bottom)` sur le panneau

**Desktop (≥ 768px) :**
- Nav horizontale inchangée
- Overlay ignoré

JS (~15 lignes vanilla) :
```js
const drawer = document.getElementById('nav-drawer');
document.getElementById('hamburger-btn').onclick = () => drawer.classList.toggle('open');
drawer.addEventListener('click', e => { if (e.target === drawer) drawer.classList.remove('open'); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') drawer.classList.remove('open'); });
drawer.querySelectorAll('a').forEach(a => a.addEventListener('click', () => drawer.classList.remove('open')));
```

### Couche 3 — Admin two-panel → onglets mobiles

Concerne : `admin/validate.html` et `admin/questions.html`

**Mobile (< 768px) :**
- Switcher onglets en haut de page (visible mobile uniquement) :
  ```
  [📋 רשימה]   [✏️ עריכה]
  ```
- Onglet "רשימה" actif par défaut
- Sélectionner une question dans la sidebar → bascule automatiquement sur "עריכה"
- Bouton "← חזור לרשימה" dans l'éditeur pour revenir à "רשימה"

**Desktop (≥ 768px) :**
- Switcher masqué, layout deux colonnes inchangé

JS (~20 lignes) : toggle `display:none` sur les panneaux `data-panel="list"` et `data-panel="editor"`.

---

## Corrections espace étudiant (page par page)

| Fichier | Problème | Fix |
|---|---|---|
| `parcours.html` | Chips seifim trop petites sur mobile | `.seif-chip` : `min-width` ajusté, padding augmenté |
| `profil.html` | `.stat-row` peut être étroit | Stack vertical sous 400px si nécessaire |
| `settings.html` | Grille options sections déborde | `grid-2` → 1 colonne sous 480px |
| `onboarding.html` | Audit visuel | Corrections si débordement constaté |
| `revision.html` | Player géré par JS (même code que chapitre) | Vérification seulement |
| `home.html` | Déjà mobile ✓ | Aucun changement |
| `chapitre.html` | Player JS — vérifier `choice-grid` sur petit écran | `.choice-grid` → 1 colonne sous 400px si nécessaire |

---

## Contraintes

- Aucune dépendance externe ajoutée
- Aucun framework CSS ou JS
- RTL respecté partout : hamburger en `inset-inline-start`, overlay s'ouvre depuis la droite
- Pas d'animation sur l'admin (apparition instantanée)
- Pas de régression desktop : tous les changements CSS sont dans des blocs `@media (max-width: 768px)` ou ajoutent des classes sans toucher les existantes
- Tests manuels dans le preview à 375px (iPhone) et 768px (tablette) après chaque page

---

## Fichiers modifiés

| Fichier | Type de changement |
|---|---|
| `static/css/styles.css` | Ajouts CSS mobile |
| `templates/admin/_layout.html` | Hamburger + overlay drawer |
| `templates/admin/validate.html` | Classe `admin-two-col` + switcher onglets |
| `templates/admin/questions.html` | Classe `admin-two-col` + switcher onglets |
| `templates/student/parcours.html` | Fix chips seifim |
| `templates/student/settings.html` | Fix grille sections |
| `templates/student/profil.html` | Fix stat-row si nécessaire |
| `templates/student/onboarding.html` | Fix si nécessaire après audit |
