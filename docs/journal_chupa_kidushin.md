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

- Statut : **généré et validé** (21 questions, 0 erreur via `question_types.normalize_imported_question`)
- Fichier : `generated_questions_ehy_26.json`
- Contenu source : seifim א (פילגש/פנויה, נישואין אזרחיים), ב (חופה בלבד), ג (נחשבת אשת איש),
  ד (קידושי ביאה, תוקף, מלקות, קידושין בלילה)
- Sujets utilisés : פילגש ופנויה ; מעמד אשה שנבעלה שלא לשם קידושין ; נישואין אזרחיים - חזקת אין
  אדם עושה בעילתו בעילת זנות ; נישואין אזרחיים ; נישואין אזרחיים - פסיקת האחרונים ; חופה בלבד
  לעניין קידושין ; מעמד אשת איש לאחר קידושין ; קידושי ביאה ; עונש המקדש בביאה, בשוק או בלא
  שידוכין ; קידושין בלילה.
- Répartition : 12 multiple_choice, 5 multiple_opinions_dropdown, 4 true_false.
- Décision de convention (à réutiliser pour les lots suivants) : ב״ש (Beit Shmuel) et ח״מ
  (Chelkat Mechokek) traités comme section `shulchan_aruch` (commentaires principaux d'Even
  haEzer, équivalent au rôle de Cha״ch/Taz pour Yoré Dé'a) ; פת״ש, באר היטב et responsa
  d'acharonim tardifs → `ptei_teshuva` ; discussions de Guemara/Rishonim (Rambam, Rosh, Ran,
  Rashba, Tosfot, Ramban...) → `tur`.
- Reste en attente : vérification haiku + Sefaria (voir section dédiée).

### Lot 2 — ehy siman 27 (לשונות קידושין)

- Statut : **généré et validé** (37 questions, 0 erreur)
- Fichier : `generated_questions_ehy_27.json`
- Contenu source : seifים א (לשונות ודאים), ג (לשונות מסופקים), ד (לא אמר "לי"), סעיף ללא מספר
  (עוד לשונות), ו (הריני אישך / הרי את חמי), ז (נתנה היא ואמרה היא / נתן הוא ואמרה היא), ט
  (קידושין בהנאת מתנה לאדם חשוב, נתנה היא ואמר הוא), י (שיעור פרוטה). Exclut le passage corrompu
  p.13 (voir anomalie ci-dessus) — aucune carte générée sur ce passage.
- Répartition : 21 multiple_choice, 11 multiple_opinions_dropdown, 5 true_false.
- Note : סעיפים ב, ה et ח du texte source n'apparaissaient pas dans l'extrait fourni (numérotation
  telle quelle dans le document) — rien à générer pour eux.

### Lot 3 — ehy siman 29 (נתינת הכסף, משכון, קנין סודר, מנה חסר, כוס, "הבה מיהבה")

- Statut : **généré et validé** (26 questions, 0 erreur)
- Fichier : `generated_questions_ehy_29.json`
- Contenu source : seifim א (מתעמ"ל / קידושין ע"מ להחזיר), ב-ה (ערב, עבד כנעני), ו (משכון, קנין
  סודר), ז (מנה/דינר), ח (מחלוקת על הסכום), ט (כוס זה), י (הבה מיהבה).
- Répartition : 17 multiple_choice, 6 multiple_opinions_dropdown, 3 true_false.

## Récapitulatif final de la génération (3 lots)

| Lot | Siman | Fichier | Cartes | Statut validation script |
|---|---|---|---|---|
| 1 | ehy 26 | `generated_questions_ehy_26.json` | 21 | 0 erreur |
| 2 | ehy 27 | `generated_questions_ehy_27.json` | 37 | 0 erreur |
| 3 | ehy 29 | `generated_questions_ehy_29.json` | 26 | 0 erreur |
| **Total** | | | **84** | |

Les 3 lots ont été générés d'un coup comme demandé (pas d'attente de jugement utilisateur entre
les lots). Reste à faire : vérification par agent Haiku (voir section dédiée — Sefaria
indisponible dans cette session, vérification limitée au texte source sauvegardé), puis import
réel via `/admin/import` après revue humaine.

## ⚠️ Contrainte réseau — API Sefaria inaccessible depuis cette session

Testé : `curl` vers `www.sefaria.org` (directement et via l'agent-proxy) renvoie **403 sur le
CONNECT** — `gateway answered 403 to CONNECT (policy denial or upstream failure)`
(`$HTTPS_PROXY/__agentproxy/status` confirme `recentRelayFailures` sur `www.sefaria.org:443`).
Selon `/root/.ccr/README.md`, un 403 du proxy signifie que l'hôte est bloqué par la politique
réseau de cette session/organisation — **il ne faut pas réessayer ni contourner**.

**Conséquence** : l'étape prévue par l'utilisateur (« un agent avec haiku va vérifier en
s'aidant de l'API Sefaria ») **ne peut pas être exécutée telle quelle** dans cet environnement.
Adaptation retenue : l'agent de vérification (Haiku) travaille uniquement à partir du texte
source déjà sauvegardé (`docs/source_texts/heichal_shlomo_chupa_vekidushin_ehy_26-27-29.txt`) et
du schéma (`question_types.py`), sans confirmation croisée Sefaria. **Il faudra qu'un humain (ou
une session avec accès Sefaria) refasse la vérification croisée Sefaria avant l'import définitif
en production.**

## Vérification (agent Haiku — texte source seul, Sefaria indisponible)

- [ ] Lot 1 — à lancer après génération
- [ ] Lot 2 — à lancer après génération
- [ ] Lot 3 — à lancer après génération

## Décisions de nommage / conventions prises pendant la génération

_(à compléter au fil de la génération — sujets réutilisés, choix de type de carte pour cas
ambigus, etc.)_
