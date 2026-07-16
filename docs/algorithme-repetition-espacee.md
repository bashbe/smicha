# Comment marche la répétition espacée de Smiha

> Ce document part de zéro. Aucune connaissance préalable n'est requise : ni en
> mémoire, ni en mathématiques, ni dans le code du projet. À la fin, tu
> comprendras **pourquoi telle carte revient tel jour** — sans avoir besoin de
> lire le code.
>
> Pour le détail d'implémentation (routes, modèle de données, format des
> questions), voir plutôt le [README](../README.md), section « Logique métier
> clé ». Ici on explique le **pourquoi** et le **comment**, pas le **où**.

---

## 1. Le problème : on oublie

Quand tu apprends quelque chose — un din de Halakha, un chiffre, une מחלוקת — tu
le sais très bien sur le moment. Puis tu l'oublies. Pas d'un coup : d'abord vite,
puis de plus en plus lentement.

C'est ce qu'on appelle la **courbe de l'oubli**. Si tu apprends une carte
aujourd'hui et que tu ne la revois jamais, ta probabilité de t'en souvenir chute
en quelques jours. Mais il y a une bonne nouvelle : **chaque fois que tu te
souviens d'une carte avant de l'avoir oubliée, tu l'oublies ensuite plus
lentement.** Le souvenir devient plus robuste, comme un muscle qui se renforce à
chaque entraînement.

Le mauvais réflexe serait de tout relire tout le temps : épuisant et inutile
(tu réviserais des choses que tu sais déjà par cœur). Le bon réflexe, c'est de
réviser chaque carte **juste avant** de l'oublier. Ni trop tôt (perte de temps),
ni trop tard (elle est déjà oubliée, il faut tout réapprendre).

## 2. L'idée de la répétition espacée

La répétition espacée, c'est exactement ça : présenter chaque carte au **bon
moment**, et espacer de plus en plus les révisions à mesure que le souvenir se
solidifie.

- Tu réussis une carte aujourd'hui → on te la remontre dans quelques jours.
- Tu la réussis encore → on attend plus longtemps (une semaine, deux semaines…).
- Tu la rates → on la ramène vite, parce qu'elle n'est manifestement pas acquise.

Les intervalles grandissent : 1 jour, puis 3, puis 8, puis 20, puis 50… Tant que
tu réussis. Le résultat : tu retiens autant (ou mieux) en révisant beaucoup
moins. C'est le cœur de toute la mécanique de Smiha.

Reste la vraie question : **comment le programme décide-t-il du bon moment ?**
C'est le travail de l'algorithme **FSRS-6**.

## 3. Le cœur : les trois grandeurs de FSRS

FSRS (*Free Spaced Repetition Scheduler*, version 6) décrit l'état de ta mémoire
pour **chaque** carte avec trois nombres. Tout le reste en découle. Le code vit
dans [`fsrs.py`](../fsrs.py).

### La rétrievabilité **R** — « est-ce que je m'en souviens là, maintenant ? »

`R` est une **probabilité**, entre 0 et 1 (0 % à 100 %). Juste après une
révision réussie, `R` vaut presque 1 (tu viens de la voir). Puis `R` baisse avec
le temps qui passe.

La formule utilisée est :

```
R(t) = (1 + FACTOR × t / S)^DECAY
```

En français : la probabilité de te souvenir dépend du **temps écoulé** `t`
depuis la dernière révision, et de la **stabilité** `S` de la carte (voir juste
après). `DECAY` et `FACTOR` sont deux constantes qui donnent sa forme à la courbe
de l'oubli (`DECAY = −w20 = −0,1542` ; `FACTOR` en découle). Tu n'as pas besoin
de les retenir — l'idée à garder est : **plus le temps passe, plus R baisse ;
plus la carte est stable, plus R baisse lentement.**

### La stabilité **S** — « à quel point ce souvenir est-il solide ? »

`S` se mesure en **jours** : c'est, en gros, le nombre de jours qu'il faut pour
que `R` retombe à ~90 %. Une carte fraîchement apprise a une petite stabilité
(quelques jours). Une carte revue dix fois avec succès peut avoir une stabilité
de plusieurs mois.

Deux règles importantes :

- **Chaque révision réussie augmente `S`** (le souvenir se solidifie). Une
  réponse rapide et sûre l'augmente plus qu'une réponse hésitante.
- **Un oubli ne peut jamais augmenter `S`.** Si tu rates une carte, sa stabilité
  ne remonte pas — c'est une garantie de l'algorithme (le « cap » de FSRS-6). On
  ne peut pas « progresser » en échouant.

### La difficulté **D** — « à quel point cette carte résiste-t-elle ? »

`D` est un nombre entre 1 (facile) et 10 (coriace). Une carte difficile gagne de
la stabilité plus lentement : il faudra la revoir plus souvent. `D` évolue un peu
à chaque réponse et tend doucement à revenir vers une valeur moyenne.

### Comment on en déduit la date de révision

C'est le point qui relie tout. On connaît la stabilité `S` de la carte et une
**cible de rétention** (par exemple 95 % — voir §7). On cherche : *dans combien
de jours R va-t-il retomber à 95 % ?* La réponse est l'intervalle :

```
intervalle = S / FACTOR × (cible^(1/DECAY) − 1)
```

À une cible de 95 %, ça revient à peu près à **`intervalle ≈ S × 0,40`**. Cette
date devient le `due_date` de la carte : le jour où elle réapparaît. Plafond
absolu : 365 jours.

> **En résumé de la §3** : R descend avec le temps, S dit à quelle vitesse, D dit
> à quelle vitesse S grandit. On planifie la carte pour le jour où R atteint ta
> cible. Tout le reste du système ne fait qu'**ajuster** ces trois nombres.

## 4. Tu ne notes rien : la note est automatique

Dans beaucoup d'applis de flashcards, tu dois t'auto-évaluer (« facile / moyen /
dur »). Pas ici. Smiha **déduit** une note de 1 à 4 à partir de deux choses :

1. **As-tu répondu juste ?**
2. **À quelle vitesse**, comparée à **ton propre temps de référence sur cette
   carte** (pas à une norme absolue, pour ne pas pénaliser un lecteur lent).

La règle (voir `rating_for` et `personal_bucket` dans [`fsrs.py`](../fsrs.py)) :

| Note | Sens | Condition | Libellé affiché |
|---|---|---|---|
| 1 | Raté | réponse fausse | 🔄 לחזור |
| 2 | Hésitant | juste mais ≥ 1/3 plus lent que ta référence | ⏱ מהסס |
| 3 | Bon | juste, vitesse normale | ✓ טוב |
| 4 | Maîtrisé | juste et ≥ 1/3 plus rapide que ta référence | ⚡ שולט |

Cette note pilote la mise à jour de `S` et `D`, donc le prochain intervalle. Une
note 4 espace beaucoup ; une note 1 ramène la carte très vite.

## 5. La vie d'une carte, du premier contact à la maîtrise

Voici le parcours concret d'une carte, tel que le gère
[`blueprints/api.py`](../blueprints/api.py). C'est la section la plus utile pour
comprendre le comportement observable.

1. **Jamais réussie.** Tant que tu n'as jamais répondu juste à une carte, la
   rater **ne crée rien** et **ne coûte rien** : 0 point, aucune planification.
   La carte reste simplement disponible et réapparaît dans la session en cours.
   On ne « punit » pas la découverte.
2. **Premier succès (activation).** La première fois que tu réponds juste, la
   carte est créée et programmée pour **le lendemain** — *sans* calcul FSRS
   encore. Tu gagnes 20 points fixes, et ton temps de réponse devient la
   **référence** de vitesse pour la suite.
3. **Le passage suivant.** Si tu réussis, FSRS s'enclenche vraiment pour la
   première fois : la note est calculée, la stabilité et la difficulté sont
   posées, et la vraie planification commence. Si tu rates, la carte repart au
   lendemain, sans pénalité, jusqu'au prochain succès.
4. **Carte engagée.** À partir de là, chaque révision compare ta vitesse à une
   moyenne glissante de tes derniers temps, met à jour `S`/`D`, et recalcule la
   date. C'est le régime FSRS normal.

Chaque carte a aussi un **état**, affiché dans ton profil :

| État interne | Libellé | Sens |
|---|---|---|
| `new` | חדש | jamais planifiée par FSRS |
| `learning` | בלמידה | en cours d'apprentissage |
| `review` | בשליטה | acquise, en révision espacée |
| `relearning` | חזרה מחדש | ré-apprise après un oubli |

## 6. Les garde-fous « maison »

FSRS brut a deux petits défauts observés en pratique. Smiha ajoute trois
garde-fous, réglables et documentés en tête de [`fsrs.py`](../fsrs.py) :

- **`CAP_FIRST` = 4 jours** — plafond du tout premier intervalle. Sans lui, une
  carte réussie brillamment du premier coup pourrait « disparaître » une semaine
  entière ; on préfère la revoir dans 4 jours max au début.
- **`WARMUP_INTERVALS` = [1, 3, 7]** — une rampe prudente sur les tout premiers
  passages, le temps que FSRS accumule assez de données pour bien faire.
- **`W7_FLOOR` = 0,15** — un plancher sur le mécanisme de « retour à la moyenne »
  de la difficulté. Concrètement : une carte ratée au départ revient vite à une
  difficulté moyenne au lieu de rester coincée. (Le réglage FSRS par défaut,
  `w7 = 0,001`, est quasi inerte.)

> Ces trois valeurs sont des **choix de produit, pas des vérités**. Elles sont
> faites pour être mesurées et ajustées (voir §10 et le rapport de recherche
> `Smiha_Path_SRS…`). Elles peuvent changer si les données montrent qu'un autre
> réglage retient mieux.

## 7. Ta cible de rétention

La « cible » de la §3 (le seuil auquel on replanifie la carte) est **réglable par
étudiant** — c'est `target_stability`. Trois niveaux :

| Cible | Nom | Effet |
|---|---|---|
| 0,92 | יעיל (efficace) | révise moins souvent, retient un peu moins |
| 0,95 | מאוזן (équilibré) | le défaut |
| 0,96 | מעמיק (approfondi) | révise plus souvent, retient plus |

Vois ça comme un **thermostat de mémoire** : plus tu montes la cible, plus les
intervalles se raccourcissent et plus tu révises — mais mieux tu retiens. C'est
un arbitrage effort ↔ rétention que chacun règle selon son objectif.

## 8. La pression de l'examen

Chaque parcours peut avoir une **date de מבחן**. À son approche, on ne laisse pas
les intervalles s'allonger tranquillement : on les **comprime** pour que tes
souvenirs soient au plus haut le jour J.

- À plus de 90 jours de l'examen : aucune compression, FSRS travaille normalement.
- À moins de 90 jours : les intervalles sont multipliés par un facteur qui
  descend de façon linéaire (`max(0,30, jours_restants / 90)`).
- **On ne planifie jamais une révision après la date de l'examen** : une carte
  due « dans 40 jours » alors que l'examen est dans 10 sera ramenée avant.

Un parcours sans date d'examen ne subit aucune pression.

## 9. La calibration collective : apprendre de tout le monde

Il reste un problème : **une carte toute neuve, on ne connaît pas encore sa vraie
difficulté.** FSRS part d'une estimation générique. Smiha fait mieux en
s'appuyant sur les réponses de **tous** les étudiants. Le code vit dans
[`calibration.py`](../calibration.py).

### Du démarrage à froid au prior fiable

On affine la difficulté d'une carte par étapes, selon le nombre de réponses
qu'elle a déjà reçues (le *gating*) :

- **Moins de 30 réponses** — on n'a presque rien : on utilise le niveau de
  difficulté déclaré à l'import (1, 2 ou 3), comme simple indice.
- **Entre 30 et 100 réponses** — assez de données pour une estimation
  provisoire via l'Elo (voir plus bas).
- **100 réponses et plus** — estimation fiable.

### Mélange, jamais substitution

Le savoir collectif **incline** la difficulté d'une carte neuve, il ne la
**dicte** jamais. Le poids du collectif (`α`) monte avec la confiance mais est
**plafonné à `ALPHA_MAX = 0,6`** : au maximum, 60 % collectif / 40 % estimation
FSRS individuelle. Ça protège du bruit tant que la cohorte d'étudiants est petite.

### L'Elo : un classement, comme aux échecs

Pour estimer la difficulté d'une carte **et** la capacité d'un étudiant, Smiha
utilise un système de type **Elo** (le classement des joueurs d'échecs). L'idée :

- Un étudiant fort qui rate une carte → la carte « gagne » en difficulté estimée.
- Une carte facile ratée par beaucoup de monde → sa difficulté monte.
- Chaque réponse ajuste **en même temps** la difficulté de la carte et la
  capacité de l'étudiant, comme deux joueurs qui s'affrontent.

### La vitesse de réponse comme signal (mais avec prudence)

Le temps de réponse en dit long sur la solidité d'un souvenir — mais il est
bruité. Smiha le **normalise** pour être juste :

- `z_item` : ta vitesse comparée à la vitesse habituelle **sur cette carte** (une
  carte longue à lire n'est pas « difficile » juste parce qu'elle prend du temps).
- `z_user` : corrigée par **ta propre vitesse de lecture** (un lecteur lent n'est
  pas pénalisé).
- Les temps aberrants sont écrêtés (en dessous de 400 ms = pas une vraie lecture ;
  au-dessus de 120 s = distraction).

## 10. Vérifier que tout ça marche vraiment

Tous les réglages ci-dessus (les garde-fous de la §6, les priors, l'Elo) sont des
**paris**. Le seul moyen de savoir s'ils retiennent mieux, c'est de **mesurer la
rétention réelle** — sinon on règle à l'aveugle.

À chaque révision d'une carte déjà engagée, Smiha enregistre le `R` que
**l'algorithme avait prédit** (`predicted_r`) à côté du résultat réel (juste /
faux). En comparant les deux sur l'ensemble des réponses, on obtient :

- le **log loss** — la mesure de référence : à quel point les probabilités
  prédites collent à la réalité (plus bas = mieux) ;
- la **rétention réelle vs prédite** — si l'algo prédit 90 % de réussite et qu'on
  observe 90 %, il est bien calibré ; un écart de plus de ~5 points signale un
  réglage à revoir.

Ces chiffres sont recalculés par le script nocturne
[`scripts/recompute_item_stats.py`](../scripts/recompute_item_stats.py) et
affichés en direct dans le tableau de bord admin (bloc « כיול ושימור »).

## 11. Et les points, alors ?

Le système de points ([`points.py`](../points.py)) **gamifie** la régularité, mais
il est conçu pour **ne jamais fausser** la mémoire ni les signaux ci-dessus :

- Trois barèmes selon le contexte : étude normale, révision du jour (plafonnée),
  révision volontaire (récompense d'autant plus faible que la carte est déjà
  fraîche en mémoire — inutile de farmer ce qu'on sait déjà).
- Le **combo** (bonnes réponses d'affilée) est **recalculé côté serveur**, jamais
  cru sur parole depuis le navigateur — sinon on pourrait gonfler ses points *et*
  polluer les signaux de vitesse.
- Un **bonus de complétion quotidienne** récompense le fait de vider ses cartes
  dues à temps — c'est la **régularité** qu'on encourage, pas le volume ni la
  vitesse brute.

## 12. Glossaire

| Terme | Signification |
|---|---|
| **Carte** | Une question associée à ta mémoire (paire étudiant × question). |
| **R** (rétrievabilité) | Probabilité de te souvenir maintenant (0–100 %). |
| **S** (stabilité) | Solidité du souvenir, en jours. Monte à chaque succès. |
| **D** (difficulté) | Résistance de la carte, 1 (facile) à 10 (coriace). |
| **due_date** | Le jour où la carte réapparaît en révision. |
| **lapse / oubli** | Une carte ratée après avoir été acquise. |
| **cible / target** | Le seuil de R auquel on replanifie (0,92 / 0,95 / 0,96). |
| **rating** | Note automatique 1–4 (raté / hésitant / bon / maîtrisé). |
| **Elo** | Classement dynamique de la difficulté des cartes et de la capacité des étudiants. |
| **prior** | Estimation de départ de la difficulté d'une carte neuve, issue du collectif. |
| **combo** | Bonnes réponses consécutives, multiplicateur de points. |
| בשליטה / בלמידה / חזרה מחדש / חדש | États d'une carte : acquise / en apprentissage / ré-apprise / neuve. |

## 13. Pour aller plus loin

- [`README.md`](../README.md) — section « Logique métier clé » : l'implémentation
  (routes, modèle de données, effets de bord de `POST /api/answer`).
- [`fsrs.py`](../fsrs.py) — l'algorithme FSRS-6 et les garde-fous produit.
- [`calibration.py`](../calibration.py) — Elo, latence, priors collectifs,
  métriques de rétention.
- [`points.py`](../points.py) — les trois barèmes de points.
- [`blueprints/api.py`](../blueprints/api.py) — le cycle de vie d'une carte, là où
  tout se recolle à chaque réponse.
- Le rapport de recherche `Smiha_Path_SRS…` — l'état de l'art (2025-2026) et les
  pistes d'amélioration (K adaptatif de l'Elo, ancrage d'échelle, modulation de la
  cible selon l'examen).
