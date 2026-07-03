# Mobile Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre l'interface entière (espace étudiant + back-office admin) pleinement utilisable sur mobile (375px–768px).

**Architecture:** Ajouts CSS ciblés dans `styles.css` + modifications de templates Jinja2 pour l'admin (hamburger nav, onglets two-panel) ; l'espace étudiant est déjà mobile-first et nécessite seulement des corrections mineures.

**Tech Stack:** Flask/Jinja2 SSR, CSS custom properties, Vanilla JS (aucune dépendance externe).

## Global Constraints

- Aucune dépendance externe ajoutée (pas de framework CSS ou JS)
- Breakpoint mobile : `max-width: 768px`
- Breakpoint très petit écran : `max-width: 400px`
- RTL respecté partout (`dir="rtl"` sur `<html>`) — utiliser `flex-start` pour "côté droit visuel"
- Pas d'animation sur l'admin (apparition/disparition instantanée)
- Aucune régression desktop : tous les ajouts CSS sont dans des `@media (max-width:...)` ou ne touchent pas les classes existantes
- Fichiers à modifier : `static/css/styles.css`, `templates/admin/_layout.html`, `templates/admin/validate.html`, `templates/admin/questions.html`, `templates/student/parcours.html`

---

### Task 1: CSS mobile — fondation admin + fix étudiant

**Files:**
- Modify: `static/css/styles.css` (append à la fin)

**Interfaces:**
- Produit: `.admin-hamburger`, `.admin-nav-items`, `#nav-drawer`, `.admin-tab-bar`, `.admin-two-col`, `.panel-hidden`, fixes `.choice-grid` et `.parcours-header-row`

- [ ] **Step 1: Append the mobile CSS block to styles.css**

Ajouter exactement ce bloc à la **fin** de `static/css/styles.css` :

```css
/* ============================================================
   MOBILE — Admin responsive
   ============================================================ */

/* Hamburger button — hidden on desktop, shown on mobile */
.admin-hamburger {
  display: none;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  padding: 0.5rem 0.625rem;
  font-size: 1.25rem;
  line-height: 1;
  color: var(--fg);
  cursor: pointer;
}

/* Nav drawer overlay */
#nav-drawer {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.5);
}
#nav-drawer.open {
  display: flex;
  justify-content: flex-start; /* RTL: flex-start = right side */
}
#nav-drawer .drawer-panel {
  width: 240px;
  height: 100%;
  background: var(--card);
  border-left: 1px solid var(--border);
  padding: var(--space-3) var(--space-2);
  padding-bottom: env(safe-area-inset-bottom);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  overflow-y: auto;
}
#nav-drawer .drawer-panel .drawer-title {
  font-weight: 700;
  padding: 0.25rem 0.75rem;
  margin-bottom: var(--space-1);
  font-family: 'Secular One', sans-serif;
}
#nav-drawer .drawer-panel a {
  display: block;
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius-btn);
  font-weight: 600;
  color: var(--fg);
}
#nav-drawer .drawer-panel a:hover { background: var(--bg); }
#nav-drawer .drawer-panel a.active { color: var(--accent); background: var(--accent-dim); }
#nav-drawer .drawer-footer {
  margin-top: auto;
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}

/* Admin tab switcher — hidden on desktop, shown on mobile */
.admin-tab-bar {
  display: none;
}
.admin-tab-bar .tab-btn {
  flex: 1;
  padding: 0.625rem;
  border-radius: var(--radius-btn);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  font-weight: 600;
  font-size: var(--text-sm);
  font-family: inherit;
  cursor: pointer;
}
.admin-tab-bar .tab-btn.active {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-dim);
}

/* Panel hidden by tab switcher */
[data-panel].panel-hidden { display: none !important; }

@media (max-width: 768px) {
  /* Containers */
  .container-wide { padding: var(--space-2); }

  /* Admin two-column grid → single column */
  .admin-two-col { grid-template-columns: 1fr !important; }

  /* Nav items hidden, hamburger shown */
  .admin-nav-items { display: none !important; }
  .admin-hamburger { display: flex !important; }
  .admin-email     { display: none; }

  /* Tab bar visible */
  .admin-tab-bar { display: flex; gap: var(--space-1); margin-bottom: var(--space-2); }

  /* Parcours header: allow wrapping */
  .parcours-header-row { flex-wrap: wrap; gap: var(--space-1); }
}

/* Choice grid: 1 column on very small phones */
@media (max-width: 400px) {
  .choice-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 2: Vérifier visuellement (resize à 375px)**

Lancer le serveur (`python app.py`), ouvrir DevTools → responsive mode → 375px. Naviguer sur `/app/home`. Vérifier qu'aucune erreur CSS n'apparaît dans la console. La page doit s'afficher correctement (la nav est déjà mobile-first — aucun changement visible à ce stade sur les pages étudiantes).

- [ ] **Step 3: Commit**

```bash
git add static/css/styles.css
git commit -m "style: add mobile CSS foundation (admin hamburger, two-col, tabs, student fixes)"
```

---

### Task 2: Admin hamburger nav

**Files:**
- Modify: `templates/admin/_layout.html`

**Interfaces:**
- Consomme: `.admin-hamburger`, `.admin-nav-items`, `.admin-email`, `#nav-drawer` (Task 1)
- Produit: hamburger `<button id="hamburger-btn">`, overlay `<div id="nav-drawer">`, JS inline

- [ ] **Step 1: Add `admin-nav-items` class to the existing `<nav>` in _layout.html**

Modifier la ligne :
```html
          <nav class="row gap-1">
```
En :
```html
          <nav class="row gap-1 admin-nav-items">
```

- [ ] **Step 2: Add hamburger button and hide email on mobile**

Modifier le bloc `<div class="row gap-2">` (les items de droite dans le header) :
```html
      <div class="row gap-2">
        <button id="hamburger-btn" class="admin-hamburger" aria-label="תפריט">☰</button>
        <span class="text-xs muted admin-email">{{ current_user.email if current_user }}</span>
        <a href="{{ url_for('auth.logout') }}" class="btn" style="background:none;color:var(--muted-foreground);">🚪 התנתק</a>
      </div>
```

- [ ] **Step 3: Add the nav drawer overlay + JS right after `</header>` and before `<main>`**

Insérer entre `</header>` et `<main class="container-wide">` :

```html
  {# Mobile nav drawer #}
  <div id="nav-drawer">
    <div class="drawer-panel">
      <div class="drawer-title">🛡️ ניהול סמיכה</div>
      {% set items = [('admin.dashboard','לוח בקרה'),('admin.questions','שאלות'),('admin.import_questions','ייבוא שאלות'),('admin.validate','אימות שאלות'),('admin.users','משתמשים')] %}
      {% for ep, label in items %}
      <a href="{{ url_for(ep) }}" class="{{ 'active' if request.endpoint == ep }}">{{ label }}</a>
      {% endfor %}
      <div class="drawer-footer">
        <a href="{{ url_for('auth.logout') }}" style="color:var(--muted);">🚪 התנתק</a>
      </div>
    </div>
  </div>
  <script>
    (function () {
      var drawer = document.getElementById('nav-drawer');
      var btn    = document.getElementById('hamburger-btn');
      if (!btn || !drawer) return;
      btn.onclick = function () { drawer.classList.toggle('open'); };
      drawer.addEventListener('click', function (e) {
        if (e.target === drawer) drawer.classList.remove('open');
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') drawer.classList.remove('open');
      });
      drawer.querySelectorAll('a').forEach(function (a) {
        a.addEventListener('click', function () { drawer.classList.remove('open'); });
      });
    })();
  </script>
```

- [ ] **Step 4: Vérifier à 375px**

Ouvrir `/admin/dashboard` à 375px. Vérifier :
- Les items de nav horizontaux sont masqués
- Le bouton ☰ est visible en haut à gauche (côté RTL)
- Cliquer ☰ → drawer s'ouvre depuis la droite avec les 5 liens
- Cliquer un lien → drawer se ferme et navigation fonctionne
- Cliquer le fond semi-transparent → drawer se ferme
- À 900px (desktop) : nav horizontale visible, ☰ masqué

- [ ] **Step 5: Commit**

```bash
git add templates/admin/_layout.html
git commit -m "feat: admin hamburger nav mobile drawer"
```

---

### Task 3: Admin validate — two-panel → onglets mobiles

**Files:**
- Modify: `templates/admin/validate.html`

**Interfaces:**
- Consomme: `.admin-two-col`, `.admin-tab-bar`, `.panel-hidden` (Task 1)
- Produit: layout responsive + tab switcher JS

- [ ] **Step 1: Replace inline grid style with admin-two-col class**

Modifier la ligne (vers ligne 19) :
```html
<div class="grid" style="grid-template-columns:320px 1fr;align-items:start;">
```
En :
```html
<div class="grid admin-two-col" style="align-items:start;">
```

- [ ] **Step 2: Add data-panel attributes to the two panels**

`<aside class="card" ...>` → `<aside class="card" data-panel="list" ...>`

`<section class="card">` → `<section class="card" data-panel="editor">`

- [ ] **Step 3: Add tab bar HTML before the grid div**

Insérer juste avant `<div class="grid admin-two-col" ...>` :

```html
<div class="admin-tab-bar" data-has-selection="{{ 'true' if selected else 'false' }}">
  <button type="button" class="tab-btn active" data-target="list">📋 רשימה</button>
  <button type="button" class="tab-btn" data-target="editor">✏️ עריכה</button>
</div>
```

- [ ] **Step 4: Add tab-switching JS at the end of the existing `<script>` block**

Dans `<script>` (après les fonctions `addChoice`, `addDecisor`), ajouter :

```js
        // Mobile tab switching
        (function () {
          var tabBar = document.querySelector('.admin-tab-bar');
          if (!tabBar) return;
          var listPanel   = document.querySelector('[data-panel="list"]');
          var editorPanel = document.querySelector('[data-panel="editor"]');

          function showPanel(which) {
            if (window.innerWidth >= 768) {
              listPanel.classList.remove('panel-hidden');
              editorPanel.classList.remove('panel-hidden');
              tabBar.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
              return;
            }
            listPanel.classList.toggle('panel-hidden', which !== 'list');
            editorPanel.classList.toggle('panel-hidden', which !== 'editor');
            tabBar.querySelectorAll('.tab-btn').forEach(function (b) {
              b.classList.toggle('active', b.dataset.target === which);
            });
          }

          tabBar.querySelectorAll('.tab-btn').forEach(function (btn) {
            btn.addEventListener('click', function () { showPanel(btn.dataset.target); });
          });

          window.addEventListener('resize', function () { showPanel('list'); });

          // If a question is already selected on page load, open editor tab
          var initial = tabBar.dataset.hasSelection === 'true' ? 'editor' : 'list';
          showPanel(initial);
        })();
```

- [ ] **Step 5: Vérifier à 375px**

Ouvrir `/admin/validate`. Vérifier :
- Onglets "📋 רשימה" / "✏️ עריכה" visibles en haut
- Par défaut : rשימה visible, עריכה masqué
- Cliquer une question dans la liste → page recharge et s'ouvre sur onglet עריכה (car `data-has-selection="true"`)
- Cliquer "✏️ עריכה" manuellement → éditeur visible, liste masquée
- À 900px : les deux panneaux côte à côte, onglets masqués

- [ ] **Step 6: Commit**

```bash
git add templates/admin/validate.html
git commit -m "feat: admin validate mobile tab switching"
```

---

### Task 4: Admin questions — two-panel → onglets mobiles

**Files:**
- Modify: `templates/admin/questions.html`

**Interfaces:**
- Consomme: `.admin-two-col`, `.admin-tab-bar`, `.panel-hidden` (Task 1)
- Produit: layout responsive + tab switcher JS (même pattern que Task 3)

- [ ] **Step 1: Replace inline grid style with admin-two-col class**

Modifier (vers ligne 62 du fichier) :
```html
<div class="grid" style="grid-template-columns:300px 1fr;align-items:start;gap:1rem;">
```
En :
```html
<div class="grid admin-two-col" style="align-items:start;gap:1rem;">
```

- [ ] **Step 2: Add data-panel attributes**

`<aside class="card" ...>` → `<aside class="card" data-panel="list" ...>`

`<section class="card">` → `<section class="card" data-panel="editor">`

- [ ] **Step 3: Add tab bar HTML before the grid**

Insérer juste avant `<div class="grid admin-two-col" ...>` :

```html
<div class="admin-tab-bar" data-has-selection="{{ 'true' if selected else 'false' }}">
  <button type="button" class="tab-btn active" data-target="list">📋 רשימה</button>
  <button type="button" class="tab-btn" data-target="editor">✏️ עריכה</button>
</div>
```

- [ ] **Step 4: Add tab-switching JS to the existing `<script>` block**

Dans `<script>` (après `addDecisor`), ajouter :

```js
        // Mobile tab switching
        (function () {
          var tabBar = document.querySelector('.admin-tab-bar');
          if (!tabBar) return;
          var listPanel   = document.querySelector('[data-panel="list"]');
          var editorPanel = document.querySelector('[data-panel="editor"]');

          function showPanel(which) {
            if (window.innerWidth >= 768) {
              listPanel.classList.remove('panel-hidden');
              editorPanel.classList.remove('panel-hidden');
              tabBar.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
              return;
            }
            listPanel.classList.toggle('panel-hidden', which !== 'list');
            editorPanel.classList.toggle('panel-hidden', which !== 'editor');
            tabBar.querySelectorAll('.tab-btn').forEach(function (b) {
              b.classList.toggle('active', b.dataset.target === which);
            });
          }

          tabBar.querySelectorAll('.tab-btn').forEach(function (btn) {
            btn.addEventListener('click', function () { showPanel(btn.dataset.target); });
          });

          window.addEventListener('resize', function () { showPanel('list'); });

          var initial = tabBar.dataset.hasSelection === 'true' ? 'editor' : 'list';
          showPanel(initial);
        })();
```

- [ ] **Step 5: Vérifier à 375px**

Ouvrir `/admin/questions`. Vérifier :
- Onglets visibles sur mobile
- La première question de la liste est auto-sélectionnée → s'ouvre sur onglet עריכה
- Navigation entre onglets fonctionne
- Filtres (en haut de page) s'affichent en colonne sur mobile grâce à `flex-wrap:wrap` déjà présent
- À 900px : deux panneaux côte à côte

- [ ] **Step 6: Commit**

```bash
git add templates/admin/questions.html
git commit -m "feat: admin questions mobile tab switching"
```

---

### Task 5: Student pages — audit + corrections ciblées

**Files:**
- Modify: `templates/student/parcours.html` (header row)
- Verify (no changes expected): `home.html`, `profil.html`, `settings.html`, `onboarding.html`, `revision.html`, `chapitre.html`

**Interfaces:**
- Consomme: `.parcours-header-row` (Task 1)

- [ ] **Step 1: Fix parcours.html header**

Dans `templates/student/parcours.html`, le header a un `<div class="row between">` qui contient le titre des sujets à gauche et streak/points à droite. Remplacer la classe pour permettre le wrapping sur très petits écrans :

Modifier :
```html
    <div class="row between">
```
En :
```html
    <div class="row between parcours-header-row">
```

- [ ] **Step 2: Verify home.html at 375px**

Ouvrir `/app/home` à 375px. Vérifier :
- Header (avatar + prénom / streak + points) : tient sur une ligne ✓
- Compteur de jours : centré ✓
- Boutons action pleine largeur ✓
- Bottom nav visible en bas ✓

Si tout est bon : pas de changement.

- [ ] **Step 3: Verify parcours.html at 375px**

Ouvrir `/app/parcours` à 375px. Vérifier :
- Header : sujet + stats ne débordent pas
- Simanim accordion cliquables (min-height 56px) ✓
- Seif-rows cliquables (min-height 44px) ✓
- Chevron RTL correct ✓

- [ ] **Step 4: Verify chapitre.html (player) at 375px**

Ouvrir un chapitre avec des questions à 375px. Vérifier :
- Texte de la question lisible
- `.choice-grid` (2 colonnes) : vérifier que les options hebräiques courtes tiennent
- Si une option déborde → le fix `@media (max-width: 400px) .choice-grid` du Task 1 s'applique automatiquement
- Score d'explication visible après réponse

- [ ] **Step 5: Verify profil.html at 375px**

Ouvrir `/app/profil` à 375px. Vérifier :
- Avatar centré ✓
- `.stat-row` (label à droite, valeur à gauche en RTL) : les deux tiennent sur une ligne ✓
- Boutons pleine largeur ✓

- [ ] **Step 6: Verify settings.html at 375px**

Ouvrir `/app/settings` à 375px. Vérifier :
- `opt-card` pleine largeur ✓
- Calendrier hébreu s'affiche correctement dans sa carte ✓

- [ ] **Step 7: Verify onboarding.html at 375px**

Ouvrir `/app/onboarding` (accessible après reset ou compte neuf). Vérifier :
- Dots de progression ✓
- `opt-card` sujets pleine largeur ✓
- Boutons Suivant/Précédent accessibles ✓

- [ ] **Step 8: Commit parcours fix (+ any other student fixes found)**

```bash
git add templates/student/parcours.html
# + tout autre fichier étudiant modifié lors des étapes précédentes
git commit -m "fix: student pages mobile layout — parcours header wrap"
```

---

### Task 6: Final verification pass + push

**Files:** Aucun (sauf corrections de bugs découverts)

- [ ] **Step 1: Full pass at 375px (iPhone SE)**

Tester chaque page dans cet ordre :
1. `/` (landing) — lisible, bouton CTA accessible
2. `/auth` — formulaire pleine largeur
3. `/app/home` — layout correct
4. `/app/parcours` — accordion + seif-rows
5. `/app/chapitre/<subject>/<siman>` — player quiz
6. `/app/revision` — player révision
7. `/app/profil` — stats
8. `/app/settings` — options
9. `/admin/dashboard` — stats + boutons
10. `/admin/questions` — onglets, éditeur tous les champs
11. `/admin/validate` — onglets, approbation
12. `/admin/import` — formulaire upload
13. `/admin/users` — tableau

Pour chaque page : pas de scroll horizontal, texte lisible, tous les boutons ont une zone de tap ≥ 44px.

- [ ] **Step 2: Pass at 768px (tablette)**

Vérifier que le breakpoint desktop se rétablit correctement : nav admin horizontale visible, two-panel côte à côte.

- [ ] **Step 3: Fix any regressions found**

Corriger inline les éventuels problèmes trouvés lors des passes de vérification.

- [ ] **Step 4: Final commit + push**

```bash
git add -A
git commit -m "fix: mobile verification pass — final adjustments"
git push origin main
```
