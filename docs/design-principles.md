# Principes de design — Card-First

Ce document formalise la direction de design en pratique dans le code (voir l'en-tête de [static/css/styles.css](../static/css/styles.css)). Il sert de référence pour juger toute nouvelle décision d'UI : si un ajout ne découle d'aucun de ces principes, c'est un signal pour reconsidérer l'ajout.

> Cette direction remplace l'ancienne direction « Siddur Digitali » (sombre/safran), abandonnée lors du redesign de juillet 2026 (spec : [2026-07-02-redesign-frontend-design.md](superpowers/specs/2026-07-02-redesign-frontend-design.md)).

## Essence du produit

Smiha est un outil de préparation sérieuse à un examen rabbinique (Halakha, Yoré Déa). Le public est un candidat adulte engagé dans une étude exigeante, en hébreu, sur une durée de plusieurs mois. Le produit doit être perçu comme rigoureux et digne de confiance — pas comme un jeu ni une app grand public. Toute décision de design se juge d'abord à l'aune de cette sobriété assumée.

## Les 5 principes

1. **Nécessaire, sinon rien.** Chaque élément visible justifie sa présence par sa fonction. Pas d'illustrations, pas de gradients, pas d'ombres portées, pas d'icônes décoratives. Un seul appel à l'action principal par écran ; l'action secondaire est un bouton ghost.

2. **La carte d'étude est le centre.** Tout l'écran d'étude sert la question : carte pleine largeur, typographie large (20px), zone de réponse en bas, navigation masquée. Les états de réponse sont sémantiques et immédiats — vert (`--success`) pour correct, rouge (`--danger`) pour incorrect, en bordure + fond à ~10 %.

3. **Deux modes, un seul système.** Light par défaut, dark via `[data-theme="dark"]` sur `<html>`. Le basculement ne change que les tokens `:root` — aucun composant ne définit de couleur en dur. Un seul accent : le bleu `--accent`, réservé à l'action et à l'état actif. Les états sémantiques (succès/erreur) restent distincts de l'accent.

4. **Typographie hébraïque comme identité.** Secular One pour les titres et chiffres-clés (compteurs, stats), Noto Sans Hebrew pour le corps. Trois tailles de corps seulement : 13 / 16 / 20 px. Le RTL est natif dans toute l'app, jamais un ajout après coup. Les grands chiffres typographiques (compteur de jours, stats profil) remplacent les cartes-widgets.

5. **Contrainte assumée plutôt que flexibilité générique.** Grille de 8 px stricte, trois radius (12 cartes / 8 boutons / 9999 pills), pas de bibliothèque CSS externe. Une variation (radius, espacement, taille) doit venir d'un token existant de `:root`, pas d'une valeur ad hoc.

## Anti-références

Ce que le design refuse délibérément d'être :
- Une app de gamification façon Duolingo (mascotte, ton enjoué, son) — le sérieux de l'examen prime sur le ludique.
- Un dashboard SaaS générique en cards interchangeables — les stats sont des lignes typographiques, pas des widgets.
- Une interface décorée — si un élément ne sert pas la lecture ou l'action, il n'existe pas.

## Comment trancher un arbitrage

Face à une nouvelle décision de design, se poser :
- Est-ce que l'élément est nécessaire à la compréhension ou à l'action, ou est-ce de la décoration ?
- Est-ce que ça réutilise un token existant (couleur, espacement, radius, taille) plutôt qu'une valeur arbitraire ?
- Est-ce que ça fonctionne dans les deux modes (light/dark) sans couleur en dur ?
- Est-ce que l'écran garde un seul appel à l'action principal ?
- Est-ce que le ton reste factuel et adapté au contexte d'un outil d'examen ?

Si la réponse est non sur l'un de ces points, la décision doit être justifiée explicitement avant d'être adoptée.

## Contrat technique

Le lecteur de questions (`static/js/chapitre.js`) et le calendrier (`static/js/hebrew-calendar.js`) génèrent leur propre markup : les classes qu'ils émettent (`.choice`, `.player-*`, `.opinions-*`, `.dot`, `.hcal-*`…) et les variables legacy (`--brand`, `--brand-dim`, `--success`, `--destructive`, `--border`, `--muted-fg`) doivent rester définies dans `styles.css` (elles sont aliasées sur les tokens canoniques).
