---
description: Génère des cartes de questions (JSON importable) à partir d'un texte source hébreu, pour n'importe quelle partie du Choulhan Aroukh, avec double vérification, bilan des retours passés et validation par question_types.py
---

# /generate-cards — Génération de cartes Smiha vérifiées

Arguments reçus : `$ARGUMENTS`
(texte source hébreu collé directement, ou chemin d'un fichier le contenant ; optionnellement
précédé de métadonnées : chelek du Choulhan Aroukh, `parcours`, `siman`, `seif`, `sujet(s)`
imposés, nombre de questions N.)

## Étape 0 — Prérequis et périmètre

1. Lis **en entier** `prompt_generation_questions.md` (racine du repo). Le « Prompt système »
   qu'il contient est TON cahier des charges : rôle, workflow en 5 passes, politique de choix
   des types, règles pédagogiques, contraintes de format et schémas JSON. Applique-le à la lettre.
2. **Détermine le périmètre** (n'importe quel chelek du Choulhan Aroukh — Orah'h 'Haïm, Yoré Dé'a,
   Even haEzer, 'Hochen Mishpat) :
   - Si `$ARGUMENTS` précise `chelek` / `parcours` / `siman`, utilise-les.
   - Sinon, demande à l'utilisateur : quelle partie du Choulhan Aroukh, quel(s) siman(im), et le
     code `parcours` à utiliser (ou à créer) côté app.
   - Vérifie si ce `parcours` est déjà enregistré :
     ```bash
     python3 -c "from question_types import VALID_PARCOURS, PARCOURS_LABELS; print(VALID_PARCOURS); print(PARCOURS_LABELS)"
     ```
   - S'il **n'existe pas encore**, propose à l'utilisateur un code (snake_case, ex.
     `hilkhot_shabbat`), un libellé hébreu et une courte description hébraïque (avec la plage de
     simanim), puis, **après confirmation**, ajoute-le à quatre endroits (jamais sans
     confirmation — c'est une modification de code partagé) : `VALID_PARCOURS`,
     `PARCOURS_LABELS` et `PARCOURS_DESCRIPTIONS` dans `question_types.py`, et `PARCOURS_LABELS`
     dans `static/js/chapitre.js`. Mets aussi à jour la liste de `VALID_PARCOURS` dans le README
     (`## Règles de maintenance`). Ne touche à rien d'autre dans ces fichiers.
3. **Sujets déjà en usage pour ce siman** : interroge la table `Subject` (le JSON
   `siman_seif_topics.json` ne gère plus que les titres de siman affichés dans le sélecteur, pas
   le regroupement des cartes — ne t'y fie pas pour les `sujet`) :
   ```bash
   python3 - <<EOF
   import sys; sys.path.insert(0, ".")
   from app import app
   from models import Subject
   with app.app_context():
       for s in Subject.query.filter_by(parcours="<parcours>", siman=<siman>).all():
           print(s.title)
   EOF
   ```
   Réutilise **exactement** ces libellés quand le thème correspond (la moindre variation de
   chaîne crée un groupe séparé dans l'app).
4. Si `$ARGUMENTS` ne contient **aucun texte source** (ni inline, ni chemin de fichier lisible) :
   demande le texte à l'utilisateur et arrête-toi là. Ne génère JAMAIS de questions de mémoire,
   sans texte source.

## Étape 1 — Bilan des retours passés (obligatoire, avant de générer)

Le but : apprendre de TOUT retour admin déjà laissé dans `/admin/questions` — pas seulement les
rejets, aussi les commentaires laissés sur des questions approuvées — sans jamais relire deux
fois le même retour ni charger tout l'historique d'un coup (l'app peut accumuler des milliers de
questions ; seul ce qui est nouveau depuis le dernier bilan doit être lu en entier).

**Principe** : un curseur incrémental. `generate_cards_lessons.md` porte en tête un marqueur
`Dernier bilan : <timestamp ISO>` (absent au premier run → tout l'historique existant est du
backlog). Seuls les retours postérieurs à ce marqueur sont extraits **avec le contenu complet de
la question jointe** (jamais une note seule — une note du type « distracteur trop facile » ne
veut rien dire sans la carte). Ce qui persiste ensuite dans le fichier n'est jamais la donnée
brute mais la conclusion distillée : le fichier reste petit pour toujours, peu importe le volume
de questions traité au fil du temps.

1. Lis `generate_cards_lessons.md` s'il existe ; note le `Dernier bilan` en tête. Applique déjà
   les leçons qui y figurent à cette génération.
2. Extrais tous les retours admin postérieurs à ce marqueur pour ce `parcours`, question jointe
   incluse — rejets, corrections (approuvées ou non) et **notes laissées sur des questions déjà
   approuvées** (l'admin peut annoter sans rejeter) :
   ```bash
   python3 - <<'EOF'
   import sys, json
   sys.path.insert(0, ".")
   from app import app
   from models import Question, QuestionEdit

   PARCOURS = "<parcours>"
   SINCE = "<timestamp du marqueur, ou None si absent>"

   with app.app_context():
       q = QuestionEdit.query.join(Question, QuestionEdit.question_id == Question.id).filter(
           Question.parcours == PARCOURS,
           QuestionEdit.action.in_(["approved", "edited", "rejected"]),
       )
       if SINCE:
           q = q.filter(QuestionEdit.edited_at > SINCE)
       edits = q.order_by(QuestionEdit.edited_at).all()

       print(f"--- {len(edits)} retour(s) admin depuis le dernier bilan ---")
       for e in edits:
           question = Question.query.get(e.question_id)
           if not e.note and e.action != "rejected":
               continue  # pas de commentaire = rien à apprendre de cette approbation muette
           print(json.dumps({
               "action": e.action,
               "note": e.note,
               "edited_at": e.edited_at.isoformat(),
               "siman": question.siman if question else None,
               "seif": question.seif if question else None,
               "question": (question.as_dict() if question else None),
           }, ensure_ascii=False))
   EOF
   ```
   Les approbations sans aucune note sont exclues d'office (rien à en tirer) — seuls les rejets
   (toujours notés, cf. `blueprints/admin.py`) et les approbations/éditions **avec** commentaire
   remontent.
3. **Si le backlog est gros** (première exécution sur un historique existant, ou long silence) :
   traite-le par lots d'environ 150 retours. Après chaque lot, met à jour
   `generate_cards_lessons.md` (étape 4) et avance le marqueur `Dernier bilan` au dernier
   `edited_at` traité, avant de charger le lot suivant — jamais tout l'historique en mémoire en
   même temps.
4. **Analyse** chaque lot (note + carte réelle, pas la note seule) : cherche des motifs récurrents
   — type mal choisi, section mal attribuée, distracteur trop faible, formulation qui trahit la
   réponse, explication insuffisante, sujet mal orthographié/dupliqué, mais aussi ce que les
   approbations commentées valident positivement (ex. « bon niveau de difficulté sur ce genre de
   machloket »). Cherche les motifs à travers tout le lot, pas question par question.
5. **Met à jour `generate_cards_lessons.md`** : pour chaque motif récurrent identifié (≥2
   occurrences dans l'historique cumulé, ou 1 occurrence clairement généralisable), ajoute ou
   renforce une entrée courte et actionnable, groupée par thème (ex. `## Sections`,
   `## Distracteurs`, `## Type de carte`). Ne duplique pas une leçon déjà présente ;
   reformule/fusionne si besoin — le fichier grandit en qualité, pas en volume. Avance le
   marqueur `Dernier bilan` au timestamp du dernier retour traité. Ce fichier n'est PAS un
   fichier de travail comme `generated_questions_<siman>.json` : commite-le (ou propose de le
   commiter) pour qu'il profite aux sessions futures.
6. S'il n'y a encore aucun retour en base pour ce parcours (cas normal pour un nouveau chelek),
   dis-le simplement à l'utilisateur et continue avec le cahier des charges seul.

## Étape 2 à 6 — Workflow du prompt de référence

Déroule les 5 passes du prompt système, dans l'ordre, sans en sauter, **en tenant compte des
leçons de l'Étape 1** :

1. **Lire, comprendre et catégoriser** le texte source en entier ; inventorier chaque din,
   machloket, chiffre légal, cas limite ; étiqueter chaque passage avec sa section selon les
   règles EXAM_SECTION ATTRIBUTION du prompt (`tur` = Tour + Beit Yossef + rishonim + guemara ;
   `shulchan_aruch` = Choul'han Arou'h + Cha'h + Taz ; `ptei_teshuva` = a'haronim postérieurs ;
   `psikei_admur` = tous les avis Habad — n'attribue cette section que si le chelek traité en a
   effectivement, sinon ignore-la). **Ignorer les notes de bas de page.** Tout passage
   impossible à classer avec certitude → demander à l'utilisateur, ne jamais deviner.
2. **Générer les questions** — couverture exhaustive par défaut (chaque din distinct → au moins
   une carte), ou exactement N si l'utilisateur l'a fixé. Jamais plus de cartes que le texte ne
   le justifie ; variantes d'un même din uniquement quand c'est nécessaire (carte complémentaire
   d'une autre section, carte de discrimination). Politique de types :
   machloket réelle entre poskim → `multiple_opinions_dropdown` ; défaut → `multiple_choice` ;
   `true_false` seulement si vraiment pertinent (minorité du lot).
   **Une seule section par carte** ; un din commun à deux parties du texte → une carte
   `shulchan_aruch` + une carte complémentaire `tur` (angle différent, pas un doublon).
   **`tags`** : ce champ nourrit désormais les *tags cachés* (voir CLAUDE.md, système de
   tags à deux niveaux) — génère-en **beaucoup, sans retenue**, quitte à ce qu'ils se
   ressemblent fortement d'une carte à l'autre ou entre cartes voisines (ratisser large :
   favorise le rappel, pas la précision). Ne cherche PAS à limiter à 2-3 tags par carte ici
   — cette contrainte d'affichage est gérée en aval par les *tags visibles*
   (`/admin/tags`, skill `/tag-clustering`), jamais par la génération elle-même.
3. **Repasser sur le texte source** et auditer chaque question (fidélité, pertinence, bon type,
   bonne section).
4. **Générer puis auditer les réponses** (pas trop faciles, halakhiquement exactes, distracteurs
   homogènes, une seule interprétation possible, aucune formulation qui trahit la réponse).
5. **Relecture linguistique hébreu + schéma** (grammaire, accords, registre, zéro lettre latine),
   puis **contrôle de couverture par section** : pour chaque section prise isolément, un
   étudiant qui n'a sélectionné que celle-là doit être interrogé sur tout ce que le texte de sa
   section enseigne — combler les trous avant livraison.

## Étape 7 — Validation par le code du repo (obligatoire)

Écris le lot dans le scratchpad puis valide-le avec le validateur réel :

```bash
python3 - <<'EOF'
import json, sys
sys.path.insert(0, ".")
from question_types import normalize_imported_question

with open("<scratchpad>/generated_questions.json", encoding="utf-8") as f:
    batch = json.load(f)

errors = 0
for i, q in enumerate(batch, 1):
    res = normalize_imported_question(q)
    if not res["valid"]:
        errors += 1
        print(f"Question {i}: {res['issue']}")
print(f"{len(batch)} questions, {errors} erreur(s)")
EOF
```

- S'il y a la moindre erreur : corrige les questions concernées et revalide, jusqu'à
  `0 erreur(s)`. N'affiche jamais à l'utilisateur un lot qui ne passe pas.

## Étape 8 — Livraison par lots, sous le jugement de l'utilisateur

1. **Livre les cartes par petits groupes de seifim traitant du même sujet** (le `sujet` est le
   critère de tri des cartes dans l'app) — pas tout le texte d'un coup. Après chaque lot,
   **attends le jugement de l'utilisateur** (validation, corrections, suppression) avant de
   passer au groupe suivant. Reste concis : les cartes parlent d'elles-mêmes.
2. Écris chaque lot validé dans `docs/generated_questions/generated_questions_<siman>.json`
   (fichier de travail : ne le commite pas, sauf demande explicite) et envoie-le à
   l'utilisateur avec un résumé bref : nombre de cartes, répartition type/difficulté/section,
   sujets utilisés, et tout choix notable ou passage non classé nécessitant son arbitrage.
3. Rappelle que l'import se fait via `/admin/import` (prévisualisation avant confirmation), et
   que le vrai jugement qualité (approbation/rejet dans `/admin/questions`) nourrira le bilan de
   l'Étape 1 lors du prochain lancement de `/generate-cards`.
