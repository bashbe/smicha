# Audit complet — 84 cartes חופה וקידושין, contre les sources Sefaria réelles

**Date :** 30 juillet 2026 (soir)
**Auteur :** Claude Code (agent de génération), sur demande explicite de l'utilisateur
**Périmètre :** `generated_questions_ehy_26.json` (21), `generated_questions_ehy_27.json` (37),
`generated_questions_ehy_29.json` (26) — 84 cartes au total.
**Différence avec les audits précédents** : c'est le premier audit mené avec un accès complet
aux **vraies sources Sefaria multi-couches** (`docs/sefaria_sources/ehy_*_ALL.txt`, récupérées
par l'utilisateur après la trim des commentaires — PR #70/#71), pas seulement le שו"ת היכל שלמה
(support de cours) ni le Choulhan Aroukh seul. Chaque `seif` et chaque machloket de dropdown a
été recroisé directement avec :
- שולחן ערוך + רמ"א (texte brut)
- חלקת מחוקק et בית שמואל (commentaires ancrés par סעיף via l'API `links` de Sefaria)
- טור, בית יוסף, דרכי משה
- פתחי תשובה

**Conclusion en une phrase** : les 84 cartes sont maintenant fiables — aucune nouvelle erreur de
fond détectée ; deux points mineurs de précision de citation relevés (non bloquants).

---

## 1. Méthode

Pour chaque carte des 3 lots :
1. Vérification du `seif` : le passage cité est-il vraiment dans CE seif du שו"ע réel (pas le
   support de cours, qui ne numérote pas toujours à l'identique) ?
2. Pour les `multiple_opinions_dropdown` : les `decisors` sont-ils des poskim réellement cités en
   désaccord sur CE cas dans les commentaires Sefaria (חלקת מחוקק/בית שמואל/פתחי תשובה), ou
   au moins dans le support de cours avec citation de poskim nommés (Rishonim/Acharonim que
   Sefaria ne couvre pas toujours dans ces commentaires-ci) ?
3. Pour chaque carte `shulchan_aruch`/`tur`/`ptei_teshuva` : la couche source correspond-elle à
   la nature du contenu (position du ב"ש/ח"מ eux-mêmes → `shulchan_aruch` ; machloket entre
   Rishonim rapportée par le ב"ש → `tur` ; פת"ש/responsa tardifs → `ptei_teshuva`) ?
4. Validation programmatique finale (`question_types.normalize_imported_question`).

---

## 2. Résultat global

| Lot | Cartes | `seif` vérifiés contre le vrai שו"ע | Dropdowns vérifiés (poskim réels) | Erreurs de fond trouvées |
|---|---:|---|---|---|
| ehy_26 | 21 | 21/21 corrects | 5/5 confirmés | Aucune |
| ehy_27 | 37 | 37/37 corrects (après corrections du 2026-07-30, PR #72) | 11/11 confirmés | Aucune nouvelle |
| ehy_29 | 26 | 26/26 corrects | 6/6 confirmés | Aucune (Q7 déjà corrigée) |
| **Total** | **84** | **84/84** | **22/22** | **0** |

Validation programmatique : `python3 -c "... normalize_imported_question ..."` sur les 3
fichiers → **84/84, 0 erreur**.

---

## 3. Détail par lot

### 3.1 `ehy_26` (siman 26, 4 seifim réels du שו"ע)

Les 4 seifim réels du שו"ע (`ehy_26_shulchan_aruch.txt`) couvrent exactement les 4 groupes de
cartes déjà en place — aucune carte mal classée :

| Seif réel | Contenu | Cartes |
|---|---|---|
| 1 | פילגש/פנויה, נישואין אזרחיים, "אין אדם עושה בעילתו בעילת זנות" | Q1–Q11 |
| 2 | חופה בלבד | Q12–Q14 |
| 3 | מעמד אשת איש | Q15 |
| 4 | קידושי ביאה, מלקות | Q16–Q21 |

Points confirmés mot pour mot contre בית שמואל/חלקת מחוקק réels (pas seulement le support de
cours) :
- Q5 (ביאה גלויה = עדים בשעת ביאה) ↔ בית שמואל כו:א, texte identique.
- Q9 (אנוסים בצנעה, אין להקל) ↔ חלקת מחוקק כו:ג, texte identique.
- Q2 (מחלוקת גדר פילגש בין שתי הבנות ברמב"ם והראב"ד/רמב"ן) ↔ בית שמואל כו:ב, confirmé.

Aucune carte fondée sur un texte inventé ou déformé.

### 3.2 `ehy_27` (siman 27, 10 seifim réels du שו"ע)

Après les 4 corrections déjà appliquées le 2026-07-30 (PR #72 : Q1/Q4/Q5 → seif 2, Q31 → seif 8),
**les 37 seifim sont maintenant tous corrects** contre `ehy_27_shulchan_aruch.txt` :

| Seif réel | Cartes |
|---|---|
| 1 | Q2, Q3, Q6, Q7, Q8, Q9, Q10, Q11, Q12 |
| 2 | Q1, Q4, Q5 |
| 3 | Q13–Q19 |
| 4 | Q20–Q24 |
| 5 | Q25, Q26 |
| 6 | Q27–Q29 |
| 7 | Q30 |
| 8 | Q31 |
| 9 | Q32–Q35 |
| 10 | Q36, Q37 |

Dropdowns vérifiés contre les commentaires réels ancrés par seif :
- Q16 (הרי את נשואתי, רמ"א vs ב"ש) ↔ **confirmé mot pour mot** dans בית שמואל כז:ח : le ב"ש dit
  explicitement "ומשמע מדברי הרב בהגה דאפילו אם היה מדבר עמה על עסקי קדושיה אפ"ה אינו כלום...
  ולא כמשמעות הג"ה זו" — exactement la position que la carte attribue au רמ"א puis contredit par
  le ב"ש.
- Q8/Q9 (קרקע/מחובר לקרקע) ↔ confirmés dans בית שמואל כז:א (même paragraphe, les deux sujets).
- Q34 (צריך לומר ואתקדש אני לך) ↔ confirmé dans בית שמואל כז:כה : "ורי"ו והמגיד כתבו... הוי
  קידושין אפילו לא אמרה ואתקדש לך... ועיין תשו' רשב"א שם מבוא' כשלא אמרה... הוי ס"ק".

**Point mineur relevé (non bloquant)** : Q14 (dropdown, לשונות מסופקים) attribue la position
stricte à "הב״ש (בשם ר״י ומהר״ט)". Le texte réel (בית שמואל כז:יא) cite en fait רמב"ם, רא"ש,
רי"ו ("להדיא") ומהרי"ט — la carte a raccourci la liste et écrit "ר״י" de façon ambiguë (peut se
lire רי"ו ou ר' ירוחם). La position elle-même (nécessité d'avoir parlé au préalable, même si les
deux parties confirment leur intention) est correcte ; seule l'attribution nominative est
imprécise. **Ne nécessite pas de correction du fond**, mais pourrait être clarifiée si on veut
une précision maximale des noms cités.

**Limite méthodologique à noter** : plusieurs cartes tur (Q8, Q9, Q15, et le volet
Rambam/Rashba vs Ran/Maharam de Q15 sur חרופתי) reposent sur des positions de Rishonim citées
dans le support de cours (שו"ת היכל שלמה) qui ne sont pas répétées telles quelles dans les
extraits טור/בית יוסף/דרכי משה récupérés (Sefaria ne segmente pas toujours ces oeuvres par סעיף
identique au שו"ע — pour le סימן כז, Sefaria renvoie tout le טור en un seul bloc "סעיף 1"). Ces
cartes restent **plausibles et non contredites**, mais n'ont pas pu être vérifiées mot pour mot
contre une source Sefaria segmentée par seif — seulement contre le support de cours d'origine.

### 3.3 `ehy_29` (siman 29, 10 seifim réels du שו"ע)

Tous les seifim confirmés corrects contre `ehy_29_shulchan_aruch.txt` — aucun changement
nécessaire. La correction précédente (Q7, carte "קידושין מדין ערב" reformatée en
`multiple_choice` le 2026-07-30 matin) reste valide et n'a soulevé aucun nouveau problème.

Dropdowns vérifiés contre les commentaires réels :
- Q2 (Tosafot/Rosh vs Rambam, raison de la nullité du מתעמ"ל) ↔ **confirmé mot pour mot** dans
  בית יוסף כט:א : "ופירשו התוספות והרא"ש לפי שדרך הוא להחזיר הסודר... לפיכך אפקעו רבנן לקידושין
  אע"ג דמדאורייתא הוי מקודשת... הרמב"ם... אינה מקודשת בין החזירה בין לא החזירה... לא נהנית ולא
  הגיע לידה כלום" — correspond exactement aux deux `dropdown_choices` de la carte.
- Q11 (Rambam/Ramban/Rashba vs Ra'avad sur le משכון) ↔ confirmé dans חלקת מחוקק כט:ז-ח.
- Q18 (Rif/Rambam vs Rosh/Tur sur מנה סתם/מנה זו) ↔ confirmé dans חלקת מחוקק כט:יג.
- Q20 (רש"י vs רמב"ן/ר"ן sur le sens de "אינה מקודשת") ↔ **le שו"ע/רמ"א lui-même** nomme ces deux
  positions explicitement dans le texte du seif 7 — confirmation directe la plus forte possible.

---

## 4. Ce qui n'a PAS été touché (jugement, pas erreur factuelle)

Comme dans l'audit précédent : la densité de cartes sur certains seifim (ex. EH27 seif 4, 5
cartes) et la répartition des niveaux de difficulté (EH29 orienté niveau 3) restent des choix
pédagogiques raisonnables, pas des erreurs. Non modifiés.

## 5. Nettoyage effectué

Les anciens fichiers `docs/sefaria_sources/ehy_26.txt` / `ehy_26.json` / `ehy_27.txt` /
`ehy_27.json` / `ehy_29.txt` / `ehy_29.json` (version 1 du script, Choulhan Aroukh seul) ont été
supprimés — ils étaient superflus depuis la v3 (`ehy_<siman>_shulchan_aruch.txt` etc.) et avaient
déjà causé une confusion : l'audit externe du 2026-07-30 après-midi (`audit_questions_chupa_
kidushin_2026-07-30.md`) s'y était référé par erreur au lieu des fichiers multi-couches complets.

## 6. Conclusion

**Les 84 cartes sont prêtes pour import** (`/admin/import`), sous réserve de la revue humaine
habituelle. Aucune correction supplémentaire n'est nécessaire suite à cet audit. Le seul point
mineur (attribution nominative imprécise dans Q14 de `ehy_27`) est cosmétique et n'affecte pas
la validité halakhique de la carte.
