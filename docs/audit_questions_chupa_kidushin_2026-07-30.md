# Audit des lots de questions — חופה וקידושין

**Date :** 30 juillet 2026  
**Périmètre :** `generated_questions_ehy_26.json`, `generated_questions_ehy_27.json`, `generated_questions_ehy_29.json`  
**Total examiné :** 84 questions  
**Décision recommandée :** corriger les métadonnées signalées avant import ; le contenu halakhique est globalement solide.

---

## 1. Méthode et sources contrôlées

L’audit a porté sur quatre niveaux :

1. **Validité technique** : chaque objet a été passé à `question_types.normalize_imported_question()`.
2. **Structure pédagogique** : type de carte, réponse correcte, distracteurs, niveau de difficulté, répétitions et regroupement par sujet.
3. **Fidélité du contenu** : comparaison avec le support de cours complet `docs/source_texts/heichal_shlomo_chupa_vekidushin_ehy_26-27-29.txt`.
4. **Référence au texte de base** : contrôle des סעיפים dans `docs/sefaria_sources/ehy_26.txt`, `ehy_27.txt` et `ehy_29.txt`.

Le support de cours est la source nécessaire pour les questions sur les ראשונים, אחרונים et les cas pratiques : les fichiers Sefaria ne contiennent, eux, que le texte du שולחן ערוך. Une question fondée sur une distinction du בית שמואל ou sur un responsum ne peut donc pas être vérifiée uniquement contre le fichier Sefaria.

Le passage corrompu, hors sujet (מקוואות), présent dans le support du סימן כז n’a pas été repris dans les questions.

---

## 2. Résultat global

| Lot | Questions | Schéma | Fidélité de fond | Problèmes bloquants |
|---|---:|---|---|---|
| `ehy_26` | 21 | 21/21 valides | Aucun écart relevé | Aucun |
| `ehy_27` | 37 | 37/37 valides | Bon ensemble ; une nuance à expliciter | 4 métadonnées `seif` erronées |
| `ehy_29` | 26 | 26/26 valides | Aucun écart relevé | Aucun |
| **Total** | **84** | **84/84 valides** | **Très bon niveau général** | **Corriger le classement du lot 27** |

Il n’existe ni question strictement dupliquée, ni objet JSON invalide, ni `multiple_opinions_dropdown` sans désaccord réel dans les trois fichiers actuels.

---

## 3. Corrections nécessaires avant import

### 3.1. Erreurs de `seif` dans `generated_questions_ehy_27.json`

Ces erreurs n’altèrent pas la réponse halakhique, mais elles faussent le classement, les filtres admin, les statistiques par סעיף et l’affichage étudiant.

| Question | `seif` actuel | `seif` correct | Justification dans le texte Sefaria |
|---|---:|---:|---|
| Q1 — `הרי את קנויה לי` | 1 | **2** | Le libellé `הרי את קנויה לי` est explicitement dans EH 27 סעיף ב. |
| Q4 — compréhension de `הרי את מקודשת` | 1 | **2** | La règle « אם הבינה דבריו… אבל האיש אינו נאמן… » est la הגה du סעיף ב. |
| Q5 — l’homme nie son intention | 1 | **2** | Cette règle est également la fin de la הגה du סעיף ב. |
| Q31 — `נתן הוא ואמרה היא` | 7 | **8** | EH 27 סעיף ח commence exactement par `נתן הוא ואמרה היא`. Le סעיף ז concerne `נתנה היא לו כסף ואמרה`. |

**Action :** modifier uniquement les quatre valeurs `seif` ci-dessus. Les textes, réponses et explications de ces cartes peuvent rester identiques.

### 3.2. Nuance à réécrire — EH 27, Q4

La carte oppose :

- le **ב״ח et le ב״ש** : la femme serait toujours crue lorsqu’elle dit ne pas avoir compris ;
- le **ח״מ / רמ״א** : elle ne le serait jamais pour `הרי את מקודשת`.

Le support de cours ajoute cependant une réserve importante du **ב״ש** : si l’on sait qu’elle comprend לשון הקודש et que la formule `הרי את מקודשת` a été employée, le ב״ש conclut à des קידושין ודאיים. La formulation actuelle est donc trop absolue pour le ב״ש.

**Action recommandée :** ajouter dans la réponse du ב״ש la condition « כאשר ידוע שהיא מבינה לשון הקודש », ou présenter explicitement le cas où elle affirme ne pas comprendre la langue / le sens de la formule. Le niveau 3 et le format `multiple_opinions_dropdown` restent pertinents.

---

## 4. Audit détaillé par lot

### 4.1. `generated_questions_ehy_26.json` — 21 questions

**Répartition actuelle :** 12 QCM, 5 cartes de positions, 4 vrai/faux ; difficultés 1/2/3 = 4 / 9 / 8.

| Partie | Questions | Verdict |
|---|---|---|
| פילגש, פנויה et mariage civil | Q1–Q11 | Conforme au support ; les distinctions entre גאונים, רמב״ם, ראב״ד, רמב״ן et פוסקים modernes sont réelles. |
| חופה seule | Q12–Q14 | Bonne progression : règle du שו״ע, débat des ראשונים, puis cas de l’אלמנה. |
| Statut après kiddushin | Q15 | Carte simple, utile et correctement placée. |
| קידושי ביאה et nuit | Q16–Q21 | Cas distincts et non redondants : validité de principe, sanction, puis question de nuit, distinction כסף/שטר et pratique. |

**Qualité pédagogique.** Le lot alterne des fondamentaux (Q1, Q4, Q15, Q21), des applications (Q5, Q8, Q9, Q12, Q16) et des machlokot réelles. Les distracteurs sont généralement plausibles sans être trompeurs de façon artificielle. La densité sur le סעיף א est élevée (11/21), mais elle reflète la longueur du support et ne crée pas de doublon exact.

**Verdict :** prêt après contrôle humain normal ; aucune correction détectée.

### 4.2. `generated_questions_ehy_27.json` — 37 questions

**Répartition actuelle :** 19 QCM, 10 cartes de positions, 8 vrai/faux ; difficultés 1/2/3 = 6 / 14 / 17.

| Partie | Questions | Verdict |
|---|---|---|
| Langues certaines, silence et compréhension | Q1–Q12 | Fond juste ; Q1, Q4 et Q5 doivent être déplacées au סעיף ב. Q4 doit intégrer la réserve du ב״ש. |
| Langues douteuses | Q13–Q19 | Très bon usage des cartes de positions ; chaque carte compare des autorités ou des lectures effectivement distinctes. |
| Omission de `לי` | Q20–Q24 | Contenu fidèle. Cinq cartes sur le même noyau sont justifiées par des angles différents, mais constituent le segment le plus dense du lot. |
| Formules, inversion donneur/parleur et אדם חשוב | Q25–Q35 | Contenu utile et progressif ; Q31 doit passer au סעיף ח. |
| פרוטה | Q36–Q37 | Bon rappel de base suivi d’une nuance actuelle. |

**Densité à surveiller.** Le groupe `אמר ׳הרי את מקודשת׳ ולא אמר ׳לי׳` contient cinq cartes (Q20–Q24). Elles ne sont pas des doublons : règle principale, avis rigoureux, contexte de discussion, exemple de ידיים מוכיחות et application contemporaine. Néanmoins, si l’objectif est une révision plus courte, Q21 et Q23 peuvent être différées ou rendues optionnelles avant de supprimer une carte fondamentale.

**Verdict :** ne pas importer avant la correction des quatre `seif` et de la nuance Q4 ; ensuite, le lot est de bonne qualité.

### 4.3. `generated_questions_ehy_29.json` — 26 questions

**Répartition actuelle :** 19 QCM, 4 cartes de positions, 3 vrai/faux ; difficultés 1/2/3 = 1 / 11 / 14.

| Partie | Questions | Verdict |
|---|---|---|
| מתנה על מנת להחזיר | Q1–Q4 | Distinction claire entre le דין de base, le fondement de la machloket, l’avantage temporel et le cas où elle a donné l’objet. |
| ערב / עבד כנעני | Q5–Q9 | Les trois mécanismes sont distingués correctement. Q7 est bien un QCM dans le fichier actuel, donc ne souffre pas du défaut de type décrit dans un ancien rapport. |
| משכון et חליפין | Q10–Q16 | Très bon ensemble de cas proches ; le niveau élevé est justifié. |
| מנה, חסר, et somme discutée | Q17–Q21 | Progression cohérente du cas simple aux distinctions entre `מנה סתם`, `מנה זו` et les lectures des ראשונים. |
| כוס et `הבה מיהבה` | Q22–Q26 | Cas bien séparés et fidèles au support. |

**Difficulté.** Ce lot est le plus exigeant : 14/26 questions sont marquées niveau 3 et une seule niveau 1. C’est acceptable pour un module avancé de קידושין, mais un apprenant débutant aura peu de cartes d’entrée. Pour un parcours plus progressif, abaisser Q1 ou Q5 au niveau 1 et ajouter 2 ou 3 rappels simples serait préférable ; ce n’est pas une correction de fond.

**Verdict :** prêt après contrôle humain normal ; aucune correction factuelle détectée.

---

## 5. Qualité des types de questions

### `multiple_choice`

Les QCM traitent principalement un fait ou un cas unique. Les bonnes réponses ne sont pas systématiquement dans la même position, et les distracteurs restent liés au sujet. Les meilleures cartes d’application sont notamment EH 26 Q5/Q8, EH 27 Q19/Q31 et EH 29 Q15/Q21/Q26.

### `multiple_opinions_dropdown`

Les cartes de positions actuelles sont correctement réservées à des machlokot ou à des lectures distinctes d’un même problème. Point important : l’ancien rapport `docs/verification_ehy_29.md` reproche une Q7 de type dropdown ; la Q7 actuellement présente dans `generated_questions_ehy_29.json` est un **QCM** et ne présente plus ce défaut.

### `true_false`

Les 15 cartes vrai/faux sont courtes et vérifiables. Elles ne dominent pas les lots. Elles conviennent surtout aux règles catégoriques et aux formulations précises des פוסקים. La proportion est saine.

---

## 6. Contrôle des métadonnées et de la couverture

| Lot | Parcours | `exam_section` observés | Commentaire |
|---|---|---|---|
| EH 26 | `chupa_kidushin` (21/21) | 9 `shulchan_aruch`, 7 `tur`, 5 `ptei_teshuva` | Cohérent avec les sources mobilisées. |
| EH 27 | `chupa_kidushin` (37/37) | 21 `shulchan_aruch`, 6 `tur`, 10 `ptei_teshuva` | Cohérent dans l’ensemble ; quatre `seif` à corriger. |
| EH 29 | `chupa_kidushin` (26/26) | 15 `shulchan_aruch`, 7 `tur`, 4 `ptei_teshuva` | Cohérent avec les développements du support. |

Les titres de sujets sont en hébreu, se regroupent logiquement et ne créent pas de collision évidente entre les trois simanim.

---

## 7. Les anciens rapports de vérification ne sont plus fiables comme état courant

Les trois fichiers `docs/verification_ehy_*.md` sont utiles comme historique, mais ils ne décrivent pas fidèlement les JSON présents aujourd’hui :

- `verification_ehy_26.md` annonce 6 dropdowns et 3 vrai/faux ; le fichier courant contient **5 dropdowns et 4 vrai/faux**. Sa répartition de difficultés est aussi différente.
- `verification_ehy_27.md` annonce 28 questions `shulchan_aruch`, 5 `tur`, 4 `ptei_teshuva` ; le fichier courant contient **21 / 6 / 10**.
- `verification_ehy_29.md` décrit une Q7 dropdown problématique et des numéros de questions décalés ; le JSON courant a déjà une Q7 QCM correcte.

**Action recommandée :** régénérer ces rapports à partir des fichiers JSON réellement présents, ou les remplacer par ce rapport. Ne pas les utiliser pour approuver un import sans comparer leur date et leur contenu au JSON.

---

## 8. Plan de correction minimal

1. Dans `generated_questions_ehy_27.json`, corriger Q1, Q4 et Q5 vers `seif: 2`, et Q31 vers `seif: 8`.
2. Réécrire la réponse du ב״ש dans EH 27 Q4 avec sa condition sur la compréhension de לשון הקודש.
3. Mettre à jour ou archiver les trois anciens `verification_ehy_*.md` afin qu’ils ne donnent plus une fausse impression de validation actuelle.
4. Importer ensuite les trois lots en statut `pending`, puis procéder à une validation rabbinique/editoriale habituelle.

## Conclusion

Les 84 questions sont techniquement importables et offrent une bonne matière de révision : elles sont majoritairement atomiques, reliées à des sources identifiables, avec de vraies machlokot dans les cartes de positions et sans répétition exacte.

Le seul lot qui nécessite une intervention avant import est **EH 27**, non pas pour son fond général, mais pour quatre classements de סעיף et une nuance de formulation. Une fois ces cinq points traités, les trois lots sont recommandés pour import en file de validation.
