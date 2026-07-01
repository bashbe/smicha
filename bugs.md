1) le bandeau נרשמת בהצלחה s'affiche au début du onboarding — CORRIGÉ : supprimé le flash à l'inscription (blueprints/auth.py), inutile puisque l'inscription redirige toujours directement vers l'onboarding.
2) la mention x2 pour les streak ne s'affiche qu'à moitié — CORRIGÉ : `.player-card` avait `overflow: hidden`, qui coupait le badge `.combo-pill` positionné en léger débordement au-dessus de la carte (static/css/styles.css).
3) à la fin de l'apprentissage d'un siman, l'utilisateur ne retourne pas tout de suite à la page d'accueil — CORRIGÉ (bug plus profond que prévu) : l'écran de fin de siman plantait silencieusement en JS (static/js/chapitre.js) à cause d'un nombre passé directement à `appendChild` au lieu d'une chaîne (`state.combo` non converti en string), ce qui laissait l'utilisateur bloqué sur un écran vide sans bouton. Corrigé le type, et ajouté un retour automatique vers l'accueil ~4s après l'écran de score (avec le bouton "חזור לבית" toujours disponible pour y aller plus vite).

---
Bug additionnel trouvé en corrigeant #3 (pas dans la liste initiale) :
4) le score affiché sur l'écran de fin de siman ("X מתוך N" réponses correctes) restait bloqué à 0 même quand toutes les réponses étaient correctes du premier coup — CORRIGÉ : dans `pick()` (static/js/chapitre.js), `prevResult` était lu après avoir déjà écrasé `state.results[origIdx]` avec le résultat de la tentative en cours, donc la comparaison ne pouvait jamais être vraie. `prevResult` est maintenant capturé au tout début de `pick()`, avant toute écriture. Vérifié : écran de fin affiche désormais "3 מתוך 3 · 100%" pour 3 bonnes réponses.

5) dans le login/inscription, le bouton était trop proche du champ mot de passe — CORRIGÉ : `margin-top` du bouton submit passé de `--space-1` (8px) à `--space-3` (24px) dans `templates/auth.html`.

6) le menu était à gauche au lieu de droite sur desktop alors que l'app est RTL — CORRIGÉ : sidebar desktop passée de `left: 0` + `border-left` + `padding-left: 200px` à `right: 0` + `border-right` + `padding-right: 200px` dans `static/css/styles.css`.

7) le toggle mode clair/sombre était dans la barre de navigation — CORRIGÉ : retiré du nav (`templates/student/_layout.html`), ajouté dans la page profil (`templates/student/profil.html`) avec un label dynamique "מצב לילה / מצב יום" selon le thème actif.

8) le pourcentage de bonnes réponses dans l'écran de fin de révision était faussé car il comptait toutes les tentatives (incluant les retries) — CORRIGÉ : `today_stats` dans `blueprints/student.py` recompte désormais les cartes uniques par `question_id` ; si une carte a été tentée plusieurs fois, seule la meilleure tentative compte (correcte dès qu'une réponse est juste).

9) la page parcours n'affichait pas les stats de l'élève — CORRIGÉ : ajout d'un header en haut de `templates/student/parcours.html` avec le sujet étudié à gauche et les icônes flamme (streak) + pièce (points) à droite, dans le même format que la page d'accueil. `profile` est maintenant passé au template depuis `blueprints/student.py`.