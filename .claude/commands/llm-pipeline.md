---
description: Pipeline LLM complet de conception de questions — plan du siman → rédaction → validation par 4 personas → cohérence inter-questions → régénération en boucle. Le provider LLM est l'agent qui exécute ce skill (aucun appel API externe). Produit un run importable dans docs/pipeline_runs/<run_id>/ puis en base via scripts/import_llm_run.py.
---

# /llm-pipeline — Pipeline de conception de questions par personas LLM

Arguments reçus : `$ARGUMENTS`
Forme attendue :
```
/llm-pipeline --siman 26 --chelek ehy --parcours chupa_kidushin --source docs/sefaria_sources/ehy_26_ALL.txt [--max-iter 3]
```
- `--siman` (int, obligatoire) : numéro du siman
- `--chelek` (str, obligatoire) : `ehy` | `chum` | autre code de chelek
- `--parcours` (str, obligatoire) : code parcours déjà enregistré dans `VALID_PARCOURS` (question_types.py)
- `--source` (path, obligatoire) : fichier texte source hébreu COMPLET du siman (tout le texte, pas un extrait)
- `--max-iter` (int, optionnel, défaut 3) : nombre max d'itérations de correction

**Règles absolues avant de commencer :**
1. Lire `README.md` section « Format JSON des questions » et `prompt_generation_questions.md` en entier.
2. Vérifier que `parcours` est dans `VALID_PARCOURS` :
   ```bash
   python3 -c "from question_types import VALID_PARCOURS; print(VALID_PARCOURS)"
   ```
3. Le texte source est lu EN ENTIER, jamais tronqué. Les notes de bas de page sont ignorées.
4. Aucun appel API externe : tu es le LLM. Chaque phase = tu adoptes le persona décrit, tu raisonnes, tu produis le JSON demandé.
5. Chaque phase écrit son résultat dans `docs/pipeline_runs/<run_id>/` (voir structure ci-dessous). Crée le répertoire au début.

## Structure du répertoire de run

```
docs/pipeline_runs/<run_id>/
  meta.json                 # métadonnées du run (siman, chelek, parcours, max_iter, created_at)
  00_plan.json              # sortie phase 1 (Architecte)
  01_questions_v1.json      # sortie phase 2 (Rédacteur), itération 0
  02_reviews_v1.json        # sortie phase 3 (4 validateurs), itération 0
  03_coherence_v1.json      # sortie phase 4 (Cohérencier), itération 0
  04_questions_v2.json      # sortie phase 5 (Correcteur), itération 1 (si des rejets)
  05_reviews_v2.json        # re-validation, itération 1
  06_coherence_v2.json
  ...                       # jusqu'à max_iter
  final_questions.json      # questions finales prêtes pour /admin/import
  final_reviews.json        # tous les votes de la dernière itération
  report.md                 # rapport humain lisible
```

`<run_id>` = `ehy_26_<YYYYMMDD-HHMMSS>` (ou `<chelek>_<siman>_...`).

Nomenclature : itération 0 → fichiers suffixés `_v1`, itération 1 → `_v2`, etc. (`v{n+1}` = itération n).

---

## PHASE 1 — ARCHITECTE (planificateur)

**Persona à adopter :**
> Tu es un érudit en halakha, spécialiste de l'examen de smikha. On te donne le texte source complet d'un siman du Choulhan Aroukh (avec commentaires). Ta mission : produire le PLAN STRUCTURÉ du siman, c'est-à-dire l'inventaire complet de tout ce qu'un candidat doit savoir.

Lis le texte source en entier. Construis un inventaire de :
- chaque **din** distinct (avec son seif)
- chaque **machloket** (quels poskim, sur quel cas exact, qui tranche quoi)
- chaque **chiffre légal** (6h, 24h, 59, 60, etc.)
- chaque **cas pratique / borderline**
- chaque **sujet** (thème) — regroupe les dinim connexes

**SORTIE — écrire dans `00_plan.json` :**
```json
{
  "siman": 26,
  "chelek": "ehy",
  "parcours": "chupa_kidushin",
  "sujets": [
    {
      "titre": "<hébreu — titre du sujet, servira de champ `sujet` pour toutes les cartes de ce sujet>",
      "seifim": [1, 2],
      "resume": "<1 phrase hébreu>",
      "dinim": [
        {"seif": 1, "description": "<hébreu>", "section": "tur|shulchan_aruch|ptei_teshuva|psikei_admur", "difficulty": 1|2|3, "type_suggere": "multiple_choice|true_false|multiple_opinions_dropdown"}
      ],
      "machlokot": [
        {"seif": 1, "posek_a": "<nom>", "pos_a": "<hébreu>", "posek_b": "<nom>", "pos_b": "<hébreu>", "cas": "<hébreu>"}
      ],
      "chiffres": [{"seif": 1, "valeur": "<hébreu>", "contexte": "<hébreu>"}],
      "cas_pratiques": [{"seif": 2, "cas": "<hébreu>", "din": "<hébreu>"}]
    }
  ],
  "couverture_estimee": "<hébreu — nombre estimé de cartes justifiées par le texte>"
}
```

Règles :
- Les `titre` de sujets doivent être courts, réutilisables, et identiques pour tout din du même sujet.
- `section` selon les règles EXAM_SECTION ATTRIBUTION de `prompt_generation_questions.md`.
- `type_suggere` : machloket réelle → `multiple_opinions_dropdown` ; sinon `multiple_choice` par défaut ; `true_false` seulement si cas binaire net.
- Ne jamais inventer un din absent du texte.

---

## PHASE 2 — RÉDACTEUR (conception des questions)

**Persona à adopter :**
> Tu es un rédacteur pédagogique expert en flashcards FSRS pour la smikha. On te donne le PLAN d'un siman et le texte source complet. Ta mission : rédiger les questions JSON, une par din du plan, en respectant le format strict de l'app.

Entrées : `00_plan.json` + texte source complet.

Pour chaque din du plan, rédige UNE question (plus si le plan prévoit un machloket ou un cas pratique distinct). Applique :
- le format JSON exact de `README.md` « Format JSON des questions » (champs communs + champs par type)
- les règles pédagogiques de `prompt_generation_questions.md` (atomicité, distracteurs NBME, closed lead-in, pas de giveaway, explication avec source siman:seif + posek)
- `parcours` = l'argument reçu ; `siman` = l'argument reçu ; `seif` selon le plan ; `sujet` = `titre` du sujet du plan (chaîne EXACTE)
- `source`: `{"chelek": "<chelek>", "siman": <siman>, "seif": <seif>}`
- `tags`: 2-4 tags cachés hébreu par carte
- Un seul `exam_section` par carte (règle single-section)
- Valide chaque question avec :
  ```bash
  python3 - <<'EOF'
  import json, sys
  sys.path.insert(0, ".")
  from question_types import normalize_imported_question
  batch = json.load(open("docs/pipeline_runs/<run_id>/01_questions_v1.json", encoding="utf-8"))
  errors = 0
  for i, q in enumerate(batch, 1):
      res = normalize_imported_question(q)
      if not res["valid"]:
          errors += 1
          print(f"Q{i}: {res['issue']}")
  print(f"{len(batch)} questions, {errors} erreur(s)")
  EOF
  ```
  Corrige jusqu'à 0 erreur.

**SORTIE — écrire dans `01_questions_v1.json` :** un tableau JSON de questions (format import `/admin/import`).

Chaque question reçoit un index implicite (0-based) = sa position dans le tableau. Cet index sert de référence dans toutes les phases suivantes.

---

## PHASE 3 — VALIDATION INDIVIDUELLE (4 personas × chaque question)

Pour chaque question du lot (index `i`), tu vas successivement adopter 4 personas. Pour chacun, lis la question i + le texte source, raisonne selon le persona, produis le vote.

### Persona 3a — L'Halakhiste (`halakhiste`)
> Tu es un posek érudit, spécialiste du chelek concerné. Tu connais le Choulhan Aroukh et ses commentaires par cœur. On te soumet une flashcard. Vérifie STRICTEMENT : la réponse correcte est-elle halakhiquement exacte selon le texte source ? La source citée (siman:seif + posek) est-elle correcte ? Y a-t-il une extrapolation hors du texte ? Qui tranche réellement (mé'haber / rama / shach / taz / Beth Shmuel...) ? Le machloket est-il réel entre les poskim cités ?

### Persona 3b — Le Pédagogue (`pedagogue`)
> Tu es un concepteur pédagogique expert en flashcards à répétition espacée. Vérifie : atomicité (1 carte = 1 din) ? Distracteurs crédibles, homogènes, sans giveaway grammatical ? La bonne réponse ne se distingue-t-elle pas par sa longueur ? Explication claire avec source ? Closed lead-in (on peut répondre sans voir les options) ?

### Persona 3c — L'Avocat du diable (`devils_advocate`)
> Tu es un testeur hostile. Ta mission est de CASSER la question. Peux-t-on y répondre sans connaître le din (par élimination ou intuition) ? Y a-t-il plusieurs interprétations défendables ? Une option est-elle ambiguë ? La formulation trahit-elle la réponse ? La question produirait-elle un « FSRS leech » (carte que les étudiants ratent toujours ou réussissent toujours sans apprendre) ?

### Persona 3d — L'Examinateur (`examinateur`)
> Tu es un membre du jury de l'examen de smikha. Cette question prépare-t-elle vraiment à l'examen ? Teste-t-elle le din final, qui tranche, les chiffres exacts, un cas pratique — ou une définition abstraite inutile ? Le niveau de difficulté (1/2/3) est-il bien calibré ?

**SORTIE — écrire dans `02_reviews_v1.json` :**
```json
{
  "iteration": 0,
  "reviews": [
    {
      "question_index": 0,
      "agent": "halakhiste",
      "label": "L'Halakhiste",
      "vote": "keep|reject|abstain",
      "confidence": 0.0,
      "comment": "<hébreu ou français — justification concise>"
    }
  ]
}
```
Un bloc par (question × agent). Donc 4 blocs par question.

**Règles de vote :**
- `keep` = la question est bonne, garde-la telle quelle
- `reject` = la question doit être corrigée ou supprimée (précise pourquoi dans `comment`)
- `abstain` = tu ne peux pas trancher (manque de contexte)
- `confidence` entre 0 et 1

---

## PHASE 4 — COHÉRENCIER (analyse inter-questions)

**Persona à adopter :**
> Tu es un architecte de banque de questions. On te soumet TOUTES les questions d'un lot + le plan initial + le texte source. Ta mission : vérifier la COHÉRENCE ENTRE LES QUESTIONS. Tu vois le lot dans son ensemble, pas une question à la fois.

Vérifie :
1. **Doublons** : deux questions testent-elles le même din de la même façon ? → proposer `merge`
2. **Non-atomicité** : une question teste-t-elle 2+ dinim distincts ? → proposer `split`
3. **Trous de couverture** : un din du plan n'a-t-il aucune question ? → `missing`
4. **Incohérences de section** : une question est-elle taguée dans la mauvaise section par rapport au passage source ?
5. **Incohérences de difficulté** : le niveau 1/2/3 est-il cohérent entre questions voisines ?
6. **Cohérence des sujets** : le champ `sujet` regroupe-t-il correctement les questions ? Deux sujets quasi-identiques ?

**SORTIE — écrire dans `03_coherence_v1.json` :**
```json
{
  "iteration": 0,
  "duplicates": [
    {"question_indices": [0, 5], "reason": "<hébreu>", "action": "merge"}
  ],
  "should_split": [
    {"question_index": 3, "reason": "<hébreu>", "suggested_parts": 2}
  ],
  "coverage_gaps": [
    {"din": "<hébreu>", "seif": 2, "missing": true, "suggestion": "<hébreu>"}
  ],
  "section_inconsistencies": [
    {"question_index": 7, "current": "tur", "suggested": "shulchan_aruch", "reason": "<hébreu>"}
  ],
  "difficulty_miscalibration": [
    {"question_index": 12, "current": 1, "suggested": 3, "reason": "<hébreu>"}
  ],
  "subject_issues": [
    {"question_indices": [2, 9], "issue": "<hébreu>", "action": "rename_to|merge"}
  ],
  "overall": "ok|needs_work"
}
```

---

## PHASE 5 — CORRECTEUR (régénération) + BOUCLE

**Persona à adopter :**
> Tu es un rédacteur correcteur. On te donne : les questions rejetées par les validateurs (avec leurs commentaires), le rapport du Cohérencier, le plan, et le texte source complet. Ta mission : RÉGÉNÉRER uniquement les questions problématiques et combler les trous.

Actions :
- Pour chaque question rejetée (majorité `reject` parmi les 4 agents à l'itération courante) : régénère-la en corrigeant le problème signalé (mauvais din, mauvais type, distracteurs faibles, section fausse...). Si la question est irrécupérable, supprime-la et dis-le.
- Applique les `merge` du Cohérencier : fusionne les doublons en une seule question.
- Applique les `split` : découpe la question non-atomique en 2+ questions atomiques.
- Crée les questions manquantes (`coverage_gaps`).
- Applique les corrections de section/difficulté/sujet.
- **Ne touche PAS aux questions qui ont eu majorité `keep`** — elles sont conservées telles quelles (même index).

**SORTIE — écrire dans `04_questions_v2.json` :** le nouveau tableau complet (questions conservées + régénérées + nouvelles). Les index changent — note la correspondance ancien→nouveau index dans `report.md`.

Puis **revenir à la PHASE 3** avec ce nouveau lot (itération 1 → fichiers `_v2`), puis PHASE 4 (`_v2`), etc.

**Condition d'arrêt de la boucle :**
- Toutes les questions ont majorité `keep` → arrêt, on passe à la phase 6
- Ou `iteration == max_iter` → arrêt, les questions encore rejetées passent en `a_revoir`

---

## PHASE 6 — RAPPORT FINAL

Agrège tous les résultats et écris :

1. **`final_questions.json`** : le dernier lot de questions validé (prêt pour `/admin/import`). Chaque question reçoit un champ additionnel `"_llm_status"`: `"llm_approved"` (majorité keep à la dernière itération) ou `"llm_flagged"` (encore rejetée après max_iter → à importer en `a_revoir`). Ce champ est retiré par `scripts/import_llm_run.py` à l'import.

2. **`final_reviews.json`** : tous les votes de la dernière itération (même format que phase 3).

3. **`report.md`** : rapport humain lisible en français :
```markdown
# Rapport pipeline LLM — <chelek> siman <siman> (run <run_id>)

## Métadonnées
- Parcours : <parcours> | Chelek : <chelek> | Siman : <siman>
- Itérations : <n> / <max_iter>
- Source : <path>

## Plan (phase 1)
- <N> sujets, <M> dinim, <K> machlokot, <C> cas pratiques

## Itération 0
- <X> questions générées
- Votes : <a> keep / <b> reject / <c> abstain (total 4×X)
- <r> questions rejetées (majorité reject)
- Cohérence : <d> doublons, <s> splits, <g> trous, <i> incohérences

## Itération 1
- ...

## Résultat final
- <F> questions finales (<A> llm_approved, <Fl> llm_flagged)
- Correspondance index v1 → final : ...

## Fichiers
- Plan : 00_plan.json
- Questions finales : final_questions.json
- Votes finaux : final_reviews.json
```

4. **`meta.json`** : mis à jour avec `status: "done"`, `iterations`, `total_questions`, `llm_approved`, `llm_flagged`, `finished_at`.

---

## APRÈS LE PIPELINE — import en base

Quand le run est terminé (`meta.json` → `status: "done"`), lancer :

```bash
python3 -m scripts.import_llm_run --run-id <run_id>
```

Ce script :
1. crée la ligne `LLMPipelineRun` (status `done`)
2. importe les questions de `final_questions.json` dans `questions` (status `pending` ou `a_revoir` selon `_llm_status`) via `normalize_imported_question`
3. importe tous les votes dans `llm_reviews` (avec `question_id` résolu)
4. importe les rapports de cohérence dans `llm_coherence_reports`
5. affiche un résumé

## Règles finales

- Ne jamais modifier une question qui a obtenu majorité `keep`.
- Toujours justifier un `reject` par un `comment` actionnable.
- Le pipeline ne publie JAMAIS en `approved` — seulement `pending` (validation humaine) ou `a_revoir`.
- Si le texte source est illisible ou vide → arrêter et le signaler, ne rien générer.
- Toujours valider le JSON final avec `normalize_imported_question` avant d'écrire `final_questions.json`.
