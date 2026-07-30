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

## Anomalie relevée dans le texte source — confirmée par l'utilisateur

Dans le siman כז, **pages 13 ET 14** du document (lignes ~140–163 du fichier texte extrait) sont
des **pages mal scannées** (confirmé par l'utilisateur) :
- Page 13 (lignes 140-153) : texte clairement incohérent, parle de מחיצה של פשתן, מקוואות, מים
  שאובין, חזון איש (סי' מ"ב) — un sujet de מקוואות/עירוב sans aucun rapport avec הלכות קידושין.
- Page 14 (lignes 154-163) : à première vue plus proche du sujet (mentionne "הרי את אשתי", "הרי
  את ארוסתי", "הרי את קנויה לי"…), mais le texte s'y contredit lui-même (ex. ligne 156 affirme
  "אינה מקודשת" pour des לשונות que la guémara claire, page 8 ligne 84, affirme être ודאי
  "מקודשת") et contient des "[...]" (lacunes OCR) — donc également non fiable telle quelle.

Conformément à la règle du prompt (« tout passage impossible à classer avec certitude → ne
jamais deviner »), **aucune carte n'a été générée à partir de ces deux pages**. Vérification
faite (`grep` sur les 3 fichiers JSON pour les termes propres à la page 13, et sur les
formulations propres à la page 14) : **aucune carte des 3 lots ne dépend de ces pages** — les
mêmes dinim (chorafti, nesuati, bishvil ahava vechiba, lo diberu ve'natan bishtika...) apparaissent
de façon cohérente ailleurs dans le document (pages 15-20), et c'est cette version propre qui a
servi de source aux cartes. Il faudra que l'utilisateur revérifie le PDF original aux pages 13-14
s'il pense qu'elles contiennent un contenu distinct à couvrir séparément.

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
les lots). Vérification par agent Haiku terminée pour les 3 lots (voir section dédiée) — 1 seule
correction nécessaire (carte n°7 du lot ehy 29), déjà appliquée et revalidée. **Les 3 lots sont
prêts pour import via `/admin/import`**, sous réserve d'une dernière revue humaine (et d'une
vérification croisée Sefaria dans un environnement qui y a accès, non disponible ici).

**Important — ce que Haiku a et n'a PAS fait** : les 3 agents de vérification n'ont fait QUE
lire et rapporter (consigne explicite dans leur prompt : « Ne modifie PAS le fichier JSON toi-même
— ton rôle est de vérifier et rapporter, pas de corriger »). Ils n'ont invalidé ni modifié aucune
question directement. Le seul problème réel qu'ils ont détecté (carte n°7, lot ehy 29 — deux
libellés de cas utilisés comme si c'étaient des poskim en désaccord) a été corrigé manuellement
par l'agent de génération (moi), pas par Haiku.

## Script de récupération Sefaria pour l'utilisateur

`scripts/fetch_sefaria_text.py` (stdlib uniquement, pas de dépendance) permet de récupérer
soi-même un siman depuis l'API Sefaria, dans un environnement qui y a accès (bloquée
ici par la politique réseau de cette session — voir plus bas).

**Version 1 (2026-07-30, matin) — insuffisante** : ne récupérait que le Choulhan Aroukh. Or les
cartes sont taguées par `exam_section` : une carte `tur` ou `ptei_teshuva` restait donc
invérifiable. C'est ce qu'a relevé l'utilisateur après avoir lancé le script.

**Version 2 (2026-07-30, après-midi) — toutes les couches liées par Sefaria** : récupérait, en
plus du Choulhan Aroukh, tout commentaire que l'API `links` rattachait au siman et que
`COMMENTARY_ALIASES` reconnaissait (חלקת מחוקק, בית שמואל, פתחי תשובה, mais aussi ט"ז, ש"ך,
ביאור הגר"א).

**Confirmation en conditions réelles** : l'utilisateur a lancé
`python3 scripts/fetch_sefaria_text.py --chelek ehy --siman 26 --discover` sur sa machine. Les 4
titres codés dans `DIRECT_WORKS["ehy"]` se sont révélés **corrects du premier coup** ("Shulchan
Arukh, Even HaEzer", "Tur, Even HaEzer", "Beit Yosef, Even HaEzer", "Darkhei Moshe, Even HaEzer" —
tous OK, aucun 404). L'API `links` a renvoyé ~40 œuvres liées au siman 26, dont חלקת מחוקק (3
liens), בית שמואל (5 liens) et פתחי תשובה (8+1 liens, sous deux `collectiveTitle` différents,
tous deux bien reconnus par `COMMENTARY_ALIASES`) — la logique de découverte fonctionne comme
prévu. Ce point du script (jusque-là seulement testé hors-ligne) est donc validé pour le chelek
`ehy`.

**Version 3 (2026-07-30, soir) — limité aux 3 textes principaux** : l'utilisateur a demandé de ne
garder que חלקת מחוקק, בית שמואל et פתחי תשובה ("le reste des commentateurs ne sont pas
necessaire") — retiré ט"ז, ש"ך et ביאור הגר"א de `COMMENTARY_ALIASES`/`WORK_SECTION`/
`WORK_LABELS`. Ils ressortent désormais simplement en « non suivi » dans `--discover`, comme les
dizaines d'autres œuvres liées (Be'er HaGolah, Ba'er Hetev, Rabbi Akiva Eiger, diverses
responsa...) jamais suivies.

| exam_section | couches récupérées (v3) |
|---|---|
| `shulchan_aruch` | Choulhan Aroukh, חלקת מחוקק, בית שמואל |
| `tur` | טור, בית יוסף, דרכי משה |
| `ptei_teshuva` | פתחי תשובה |

```bash
# 1. D'abord : voir ce que Sefaria expose réellement (n'écrit rien)
python3 scripts/fetch_sefaria_text.py --chelek ehy --siman 26 --discover
# 2. Puis tout récupérer
python3 scripts/fetch_sefaria_text.py --chelek ehy --siman 26 27 29
```

Sortie par siman : un fichier `.txt` + `.json` par couche (`ehy_26_shulchan_aruch.txt`,
`ehy_26_beit_shmuel.txt`, `ehy_26_tur.txt`…) **plus un `ehy_26_ALL.txt`** groupé par section
d'examen — c'est ce dernier qu'il faut donner à un agent de vérification (une seule lecture
couvre toutes les sections). Notes de bas de page et balises HTML retirées. Générique à tout
chelek (`ehy`, `chum`, `yd`, `ohc`) — seul le chelek `ehy` a été confirmé en conditions réelles
pour l'instant.

⚠️ **Les fichiers `ehy_26.txt` / `ehy_27.txt` / `ehy_29.txt`** (sans suffixe de couche) commités
le 2026-07-30 matin viennent de la version 1 : ils correspondent au seul Choulhan Aroukh et sont
remplacés par `ehy_<siman>_shulchan_aruch.txt` depuis la v2. Ils peuvent être supprimés une fois
la v3 relancée.

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

- [x] Lot 1 (ehy 26) — **vérifié, RAS** : 21/21 validées, fidélité au texte source confirmée
  ligne par ligne, types de cartes et sections d'examen justifiés, hébreu impeccable. Rapport
  complet dans `docs/verification_ehy_26.md`. Prêt pour import.
- [x] Lot 2 (ehy 27) — **vérifié, RAS** : 37/37 validées par le script, aucune carte issue du
  passage corrompu, aucun problème de fidélité/type/hébreu détecté. Rapport complet dans
  `docs/verification_ehy_27.md`. Prêt pour import.
- [x] Lot 3 (ehy 29) — **vérifié, 1 problème détecté et corrigé** : la carte n°7 ("קידושין מדין
  ערב") était en `multiple_opinions_dropdown` mais ses "decisors" étaient en réalité deux LIBELLÉS
  DE CAS ("הלווה מנה לפלוני..." / "הרוויח זמן מלווה לפלוני...") et non deux poskim en désaccord —
  une seule et même position du Rosh Be'ah (רשב"א) distinguant deux cas, mal formatée en fausse
  machloket. Corrigée en `multiple_choice` (question posée sur le cas "הרוויח זמן מלווה" isolément).
  Revalidé : 26/26, 0 erreur. Toutes les 25 autres cartes : RAS. Rapport complet dans
  `docs/verification_ehy_29.md`.

**Leçon à retenir pour les prochaines générations** : vérifier systématiquement, pour chaque
`multiple_opinions_dropdown`, que les `decisors` sont bien des POSKIM NOMMÉS en désaccord réel sur
LE MÊME cas — jamais des libellés de cas différents habillés en "decisors". C'est l'erreur exacte
que l'étape 7 du skill `/generate-cards` (validation) ne détecte pas automatiquement (elle vérifie
la structure JSON, pas la sémantique), d'où l'utilité de la vérification humaine/agent dédiée.

Les 3 vérifications ont été lancées en parallèle (au lieu de strictement séquentielles) car
les 3 lots étaient déjà tous générés d'un coup, conformément à la consigne utilisateur. Chaque
agent vérifie uniquement à partir du texte source local et du schéma `question_types.py`
(pas d'API Sefaria, indisponible — voir plus haut).

## Décisions de nommage / conventions prises pendant la génération

_(à compléter au fil de la génération — sujets réutilisés, choix de type de carte pour cas
ambigus, etc.)_
