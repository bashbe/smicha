---
description: Regroupe les tags cachés d'un parcours par thème et propose des associations vers des tags visibles, en attente d'approbation admin dans /admin/tags
---

# /tag-clustering — Regroupement des tags cachés en tags visibles

Arguments reçus : `$ARGUMENTS` (le code `parcours` à traiter, ex. `bassar_bechalav` ;
si absent, demande-le à l'utilisateur — ne devine jamais un parcours).

## Contexte (lire d'abord si besoin)

Voir CLAUDE.md, section « système de tags à deux niveaux » : les **tags cachés**
(`HiddenTag`) sont générés en masse et sans retenue par `/generate-cards` (ils peuvent se
ressembler énormément entre eux). Les **tags visibles** (`VisibleTag`) sont ce que
l'étudiant voit et utilise pour filtrer ses révisions — il ne doit jamais y en avoir plus
de 2-3 par carte en pratique. Une `TagRule` relie un ensemble de tags cachés (logique ET ou
OU) à un tag visible. Ce skill ne fait qu'une chose : **proposer** de nouvelles `TagRule`
en statut `"suggested"` — il ne les active jamais lui-même, ne modifie jamais une règle déjà
`"active"`, et ne re-propose pas ce qu'un admin a déjà `"rejected"`.

## Étape 1 — Charger l'état existant

```bash
python3 - <<'EOF'
import sys, json
sys.path.insert(0, ".")
from app import create_app
from models import HiddenTag, Question, TagRule, VisibleTag, db, question_hidden_tags

PARCOURS = "<parcours>"
app = create_app()
with app.app_context():
    # tags cachés du parcours + nombre de cartes qui les portent
    counts = dict(
        db.session.query(HiddenTag.name, db.func.count(question_hidden_tags.c.question_id))
        .join(question_hidden_tags, question_hidden_tags.c.hidden_tag_id == HiddenTag.id)
        .filter(HiddenTag.parcours == PARCOURS)
        .group_by(HiddenTag.name).all()
    )
    print("--- tags cachés (nom: nb cartes) ---")
    for name, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{name}: {n}")

    print("--- tags visibles existants ---")
    for v in VisibleTag.query.filter_by(parcours=PARCOURS).all():
        print(v.name)

    print("--- règles déjà tranchées (active/rejected) — ne pas re-proposer ---")
    rules = TagRule.query.join(VisibleTag).filter(VisibleTag.parcours == PARCOURS).all()
    for r in rules:
        hidden = sorted(t.name for t in r.hidden_tags)
        print(f"[{r.status}] {hidden} ({r.logic}) -> {r.visible_tag.name}")
EOF
```

Si aucun tag caché n'existe encore pour ce parcours, dis-le à l'utilisateur et arrête-toi —
rien à regrouper (le parcours n'a pas encore été traité par `/generate-cards`).

## Étape 2 — Regrouper sémantiquement (raisonnement, pas de code)

À partir de la liste de tags cachés (avec leur fréquence), identifie des groupes
thématiques cohérents en hébreu. Pour chaque groupe :
- Choisis le tag visible correspondant : **réutilise un `VisibleTag` existant** dont le
  thème correspond déjà plutôt que d'en créer un proche redondant ; sinon propose un nom
  court, clair, lisible par un étudiant (pas un jargon de génération).
- Choisis la logique :
  - Un seul tag caché suffit à lui seul à indiquer le thème → `logic="or"` avec un seul tag.
  - Plusieurs formulations différentes d'un même thème (quasi-synonymes) → `logic="or"`
    avec tous ces tags cachés.
  - Le thème n'a de sens que si DEUX notions distinctes sont présentes ensemble sur la même
    carte (ex. « המתנה » ET « תבשיל ») → `logic="and"`.
- Une carte peut légitimement déclencher plusieurs tags visibles à la fois (ex. un tag cadré
  fin qui matche à la fois un thème général et un thème plus spécifique) — dans ce cas
  propose simplement plusieurs `TagRule` distinctes, pas de structure combinée.
- **Ignore** (ne propose rien pour) les tags cachés déjà couverts par une règle `active` ou
  déjà `rejected` avec exactement le même ensemble+logique+cible (vu à l'étape 1) —
  c'est une décision déjà tranchée.
- Ne force pas un regroupement pour un tag caché trop rare ou trop singulier pour appartenir
  à un thème clair (ex. 1 seule occurrence, très spécifique) — laisse-le sans règle plutôt
  que de créer un tag visible fourre-tout qui n'aiderait pas le filtrage étudiant.

## Étape 3 — Écrire les suggestions en base

```bash
python3 - <<'EOF'
import sys
sys.path.insert(0, ".")
from app import create_app
from models import HiddenTag, TagRule, db
from tags import get_or_create_visible_tag

PARCOURS = "<parcours>"
# Une entrée par groupe proposé à l'étape 2 :
# (noms des tags cachés, logique "or"/"and", nom du tag visible cible)
PROPOSALS = [
    (["<tag caché 1>", "<tag caché 2>"], "or", "<tag visible>"),
    # ...
]

app = create_app()
with app.app_context():
    created = 0
    for hidden_names, logic, visible_name in PROPOSALS:
        hidden_tags = [HiddenTag.query.filter_by(parcours=PARCOURS, name=n).first() for n in hidden_names]
        hidden_tags = [t for t in hidden_tags if t is not None]
        if not hidden_tags:
            continue
        visible = get_or_create_visible_tag(PARCOURS, visible_name)
        rule = TagRule(visible_tag_id=visible.id, logic=logic, status="suggested", source="skill")
        rule.hidden_tags = hidden_tags
        db.session.add(rule)
        created += 1
    db.session.commit()
    print(f"{created} suggestion(s) écrite(s) en statut 'suggested'")
EOF
```

Remplis `PROPOSALS` avec les groupes réellement identifiés à l'étape 2 avant d'exécuter (ne
laisse jamais les valeurs d'exemple telles quelles).

## Étape 4 — Résumer à l'utilisateur

Donne un résumé bref : nombre de suggestions créées, aperçu des regroupements (tags cachés
→ tag visible, logique), et rappelle que la validation finale (approbation ou rejet) se fait
dans l'onglet **`/admin/tags`** — rien de tout cela n'affecte les étudiants tant qu'un admin
n'a pas approuvé.
