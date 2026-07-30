# Journal — génération du parcours חופה וקידושין (chupa_kidushin)

But de ce fichier : tracer chaque action de la génération/validation des cartes du
parcours `chupa_kidushin`, pour qu'une session interrompue puisse reprendre exactement
où elle s'est arrêtée. Mis à jour au fil de l'eau, pas seulement à la fin.

## Contexte

- Source : document utilisateur `Livre_27_juil_2026.pdf` (converti en .docx), un extrait
  du שו"ת היכל שלמה – חופה וקידושין, couvrant **הלכות קידושין (Even haEzer) simanim כו, כז, כט**
  (pas de siman כח dans l'extrait fourni).
- Texte source complet extrait et sauvegardé (pour reproductibilité / vérification future) :
  `docs/source_texts/heichal_shlomo_chupa_vekidushin_ehy_26-27-29.txt` (499 lignes).
- Parcours app : `chupa_kidushin` (חופה וקידושין) — **nouveau parcours multi-chelek** : couvrira
  à terme des simanim d'Even haEzer (`ehy`) ET de 'Hochen Mishpat (`chum`). Voir CLAUDE.md,
  section « Parcours multi-chelek » pour le détail du problème structurel et le prompt de
  rappel pour un futur agent.
- Convention retenue (provisoire, documentée dans CLAUDE.md + README) : chaque question porte
  un préfixe de chelek dans `source_ref` (`"ehy סי' כו סע' א"`, `"chum סי' ... "`), et les
  fichiers de lot suivent `generated_questions_ehy_<siman>.json` / `generated_questions_chum_<siman>.json`.
- Consigne utilisateur : générer tous les lots d'un coup (pas d'attente de validation humaine
  entre les lots — faute de temps), une vérification automatique (agent Haiku + API Sefaria)
  valide chaque lot ; passer au lot suivant une fois validé.

## Étape 0 — Setup (fait)

- [x] Lu `README.md` en entier (obligatoire, CLAUDE.md) + `prompt_generation_questions.md` en entier.
- [x] Enregistré le parcours `chupa_kidushin` :
  - `question_types.py` : `VALID_PARCOURS`, `PARCOURS_LABELS`, `PARCOURS_DESCRIPTIONS` (+ note
    multi-chelek en commentaire).
  - `static/js/chapitre.js` : `PARCOURS_LABELS`.
  - `static/js/admin-question-editor.js` : `PARCOURS_LABELS`.
  - `README.md` : liste des parcours + note sur le parcours multi-chelek.
- [x] Ajouté la note + prompt de rappel pour un futur agent dans `CLAUDE.md`
  (section « Parcours multi-chelek — chupa_kidushin »).
- [x] Créé ce journal + dossiers `docs/source_texts/` et `docs/sefaria_sources/`.

## Anomalie relevée dans le texte source — à signaler à l'utilisateur

Dans le siman כז, page 13 du document (lignes ~140–153 du fichier texte extrait), le texte est
**incohérent/corrompu** : il parle de מחיצה של פשתן, מקוואות, מים שאובין, חזון איש — un sujet de
מקוואות/עירוב sans rapport avec הלכות קידושין, manifestement un artefact de conversion PDF→docx
(OCR mélangé). Conformément à la règle du prompt (« tout passage impossible à classer avec
certitude → ne jamais deviner »), **ce passage a été exclu de la génération de cartes**. Il
faudra que l'utilisateur revérifie le PDF original à cet endroit s'il veut ce contenu.

## Lots

### Lot 1 — ehy siman 26 (הלכות קידושין - avant הלכות קידושין standard, chelek Even haEzer)

- Statut : en cours
- Fichier : `generated_questions_ehy_26.json`
- Contenu source : seifim א (פילגש/פנויה, נישואין אזרחיים), ב (חופה בלבד), ג (נחשבת אשת איש),
  ד (קידושי ביאה, תוקף, מלקות, קידושין בלילה)

### Lot 2 — ehy siman 27 (לשונות קידושין)

- Statut : en attente
- Fichier : `generated_questions_ehy_27.json`
- Contenu source : seifים א (לשונות ודאים), ג (לשונות מסופקים), ד (לא אמר "לי"), סעיף ללא מספר
  (עוד לשונות), ו (הריני אישך / הרי את חמי), ז-ח (נתנה היא ואמרה היא / נתן הוא ואמרה היא), ט
  (נתנה היא ואמר הוא), י (שיעור פרוטה). Exclut le passage corrompu p.13 (voir anomalie ci-dessus).

### Lot 3 — ehy siman 29 (נתינת הכסף, משכון, קנין סודר, מנה חסר, כוס, "הבה מיהבה")

- Statut : en attente
- Fichier : `generated_questions_ehy_29.json`
- Contenu source : seifim א (מתעמ"ל / קידושין ע"מ להחזיר), ב-ה (ערב, עבד כנעני), ו (משכון, קנין
  סודר), ז (מנה/דינר), ח (מחלוקת על הסכום), ט (כוס זה), י (הבה מיהבה).

## Vérification (agent Haiku + Sefaria)

- [ ] Lot 1 — à lancer après génération
- [ ] Lot 2 — à lancer après génération
- [ ] Lot 3 — à lancer après génération

## Décisions de nommage / conventions prises pendant la génération

_(à compléter au fil de la génération — sujets réutilisés, choix de type de carte pour cas
ambigus, etc.)_
