# Service worker & mise à jour automatique des assets statiques

Date: 2026-07-10

## Contexte

L'app n'a actuellement aucune infrastructure PWA : les fichiers de `static/`
(CSS, JS, favicon) sont chargés directement via des balises `<link>`/`<script>`,
sans service worker ni manifest. Il n'y a pas de mécanisme de cache-busting :
si un navigateur met en cache un fichier statique de manière agressive, un
utilisateur peut continuer à voir une version obsolète après un déploiement.

Objectif : à chaque nouvelle version poussée en production, le service worker
doit automatiquement invalider et rafraîchir les assets statiques mis en
cache, avec une notification non-intrusive pour l'utilisateur.

## Détection de version

Au démarrage de l'app (`app.py`), `APP_VERSION` est calculé une seule fois :

1. `git rev-parse --short HEAD` (subprocess, cwd = racine du projet).
2. Si `.git` absent ou commande indisponible (ex. déploiement sans historique
   git) → fallback sur un timestamp au démarrage du process.

`APP_VERSION` est exposé aux templates via `context_processor` et utilisé pour
nommer le cache du service worker.

## Service worker

Servi par une **route Flask** `GET /sw.js` (pas un fichier statique) :

- `Content-Type: application/javascript`, `Cache-Control: no-cache, must-revalidate`
  — le fichier lui-même ne doit jamais être mis en cache par le navigateur,
  sinon la détection de mise à jour est retardée.
- Le contenu du script est généré depuis `templates/sw.js.jinja` avec
  `CACHE_NAME = f"smiha-static-{APP_VERSION}"` injecté. Comme ce nom change à
  chaque déploiement, le fichier `sw.js` change d'octets à chaque push — ce
  qui déclenche la détection native de mise à jour du navigateur (comparaison
  byte-à-byte à chaque `registration.update()`).
- Scope : `/` (racine), pour que le SW puisse un jour intercepter d'autres
  requêtes si besoin, mais en pratique :
  - **Intercepte uniquement** les requêtes `GET` dont le chemin commence par
    `/static/` → stratégie *cache-first avec mise à jour en arrière-plan*
    (stale-while-revalidate) : sert depuis le cache si présent, refetch en
    parallèle pour la prochaine visite.
  - Toute autre requête (pages HTML, `/app/*`, `/admin/*`, `/auth/*`, API)
    **n'est pas interceptée** — passthrough réseau direct. Aucune donnée
    dynamique/authentifiée n'est mise en cache par le service worker.
  - À l'événement `activate`, suppression de tous les caches
    `smiha-static-*` dont le nom ≠ `CACHE_NAME` courant.
  - Écoute un `message` de type `SKIP_WAITING` → appelle `self.skipWaiting()`
    pour activer immédiatement la nouvelle version sur demande de l'UI.

Pas de précache d'une liste figée de fichiers (`install` event ne fait rien de
spécial) : la liste des fichiers statiques change au fil du temps et une
liste manuelle serait une charge de maintenance en plus. Le cache se
construit au fil des requêtes réelles.

## UX de mise à jour (bandeau)

Script inline dans `templates/base.html` :

- `navigator.serviceWorker.register('/sw.js')` au chargement.
- Sur `registration.addEventListener('updatefound', ...)`, suit le nouveau
  worker ; quand son état passe à `installed` **et** qu'un
  `navigator.serviceWorker.controller` existe déjà (donc ce n'est pas la
  toute première installation), affiche un bandeau fixe en bas de page :
  « Nouvelle version disponible — [Actualiser] ».
- Clic sur « Actualiser » → `postMessage({type: 'SKIP_WAITING'})` au worker en
  attente, puis écoute `controllerchange` sur `navigator.serviceWorker` pour
  recharger la page (`location.reload()`) une fois le nouveau SW actif.
- Vérification périodique : `registration.update()` appelé sur
  `visibilitychange` (quand l'onglet redevient visible), en plus des
  vérifications automatiques du navigateur à la navigation.
- Le bandeau est un petit bloc HTML/CSS ajouté dans `base.html` + quelques
  règles dans `styles.css`, caché par défaut (`display: none`), affiché en JS.

## Manifest PWA

Nouveau fichier `static/manifest.json` :

- `name`: "סמיכה — הכנה לבחינה", `short_name`: "סמיכה"
- `start_url`: `/`, `display`: `standalone`, `lang`: `he`, `dir`: `rtl`
- `background_color`: `#0D1117`, `theme_color`: `#0D1117`
- `icons`: 192×192 et 512×512 PNG générés depuis `static/favicon.svg`
  (fond `#0D1117`, lettre ס en `#E07B20`), sauvegardés dans `static/images/`.

Lié dans `base.html` via `<link rel="manifest" href="...">` et
`<meta name="theme-color" content="#0D1117">`.

## Hors scope

- Pas de mode offline pour les pages dynamiques (quiz, admin, etc.).
- Pas de précache exhaustif au premier install.
- Pas de notifications push.
- Pas de Dockerfile/CI — le mécanisme s'appuie uniquement sur `git` étant
  présent dans l'environnement de déploiement (fallback timestamp sinon).

## Documentation

`README.md` reçoit une nouvelle section (après "Commandes utiles" ou dans
"Points d'attention pour un futur développeur") expliquant :
- le mécanisme de versioning (hash git → `APP_VERSION` → nom du cache SW),
- pourquoi `/sw.js` est une route Flask et non un fichier statique,
- la règle : ne jamais committer/hardcoder un nom de cache statique — tout
  est dérivé automatiquement de `APP_VERSION`.
