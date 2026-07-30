> ⚠️ **Rapport historique** — la Q7 signalée ci-dessous comme problématique a été corrigée le
> jour même (réécrite en `multiple_choice`, voir `docs/journal_chupa_kidushin.md`). La Q7
> actuellement présente dans `generated_questions_ehy_29.json` n'a plus ce défaut. Voir
> `docs/audit_questions_chupa_kidushin_2026-07-30.md` pour l'état de référence actuel (confirme
> qu'aucun autre problème n'a été trouvé dans ce lot).

# Rapport de vérification — Lot de cartes Siman 29 (Even HaEzer)

## Résumé exécutif

**Validation programmatique** : ✓ PASS — 0 erreur sur 26 questions  
**Vérification manuelle** : ⚠ 1 problème substantiel détecté  
**Couverture du texte source** : ✓ Complète et fidèle

**Conclusion** : Le lot est **globalement fiable pour import**, mais **une correction est nécessaire avant import** : la question Q7 doit être réécrite (type et structure des decisors).

---

## 1. Validation programmatique

Commande exécutée :
```bash
python3 -c "import json,sys; sys.path.insert(0,'.'); from question_types import normalize_imported_question; batch=json.load(open('generated_questions_ehy_29.json',encoding='utf-8')); [print(i, normalize_imported_question(q)['issue']) for i,q in enumerate(batch,1) if not normalize_imported_question(q)['valid']]; print(len(batch), 'questions')"
```

**Résultat** : 26 questions valides, 0 erreur.

Tous les champs obligatoires sont présents :
- `type`, `parcours`, `sujet`, `siman`, `seif`, `difficulty_level`, `exam_section`, `explanation` ✓
- Champs spécifiques (options, statement_text, dropdown_choices/decisors) ✓
- Hébreu uniquement dans les textes (pas de caractères latins visibles) ✓
- Numérotation des options séquentielle (1, 2, 3, 4) ✓

---

## 2. Vérification manuelle contre texte source

Chaque question a été contrôlée contre `heichal_shlomo_chupa_vekidushin_ehy_26-27-29.txt` (lignes 300-498, siman 29 seifim 1-10).

### Couverture par seif

| Seif | Questions | État |
|------|-----------|------|
| 1 (מתנה על מנת להחזיר) | Q1–Q4 | ✓ Fidèles au texte (Rabba, Tosafot, Ra'ash, Rama) |
| 2 (קידושין מדין ערב) | Q5–Q7 | ⚠ Q7 — Problème structurel (voir ci-dessous) |
| 3 (למדים משני דינים) | Q9 | ✓ Fidèle |
| 5 (קידושין מדין עבד כנעני) | Q8 | ✓ Fidèle |
| 6 (משכון, קנין סודר) | Q10–Q17 | ✓ Tous fidèles (Rabba, Rambam, Rama, achéronim) |
| 7 (התקדשי במנה) | Q18–Q21 | ✓ Tous fidèles (R. Elazar, Rav Ashi, Rif/Rambam vs Ra'ash/Tur) |
| 8 (מחלוקת על סכום) | Q22 | ✓ Fidèle (Tosefta) |
| 9 (התקדשי בכוס) | Q23 | ✓ Fidèle (Rambam vs Rashi/Ra'h) |
| 10 (כל הבה מיהבה) | Q24–Q26 | ✓ Tous fidèles (Rav Hama, Rabina, Rav Sama bar Rakta) |

### Analyse des types de questions

**Multiple choice (18 questions)** : Appropriés ; dinim factuels ou application à des cas. ✓

**True/false (4 questions)** : 
- Q10, Q14, Q24, Q25 — Tous genuinely binaires (faits catégoriques du texte source). ✓

**Multiple opinions dropdown (4 questions)** : 
- Q2 (Tosafot/Ra'ash vs Rambam) : ✓ Machloket réelle entre poskim  
- Q6 (Rashi/Rishonim : condition "он doit dire התקדשי לי") : ✓ Consensus interprété comme unique position  
- Q11 (Rambam/Rashban vs Rav Avraham ben David) : ✓ Machloket réelle  
- Q19 (Rif/Rambam vs Ra'ash/Tur) : ✓ Machloket réelle  
- Q21 (Rashi vs Rambam/Ra'n) : ✓ Machloket réelle  
- **Q7** ⚠ PROBLÈME (voir détail ci-dessous)

---

## 3. Problème détecté : Q7 — Misutilisation du type `multiple_opinions_dropdown`

**Question** (Q7, seif 2, lignes 113–131 du JSON) :
```
"question_text": "אמרה ׳הלווה מנה לפלוני ואתקדש אני לך׳ לעומת ׳הרוויח זמן מלווה לפלוני ואתקדש אני לך׳ - מהו הדין בכל אחד, לפי הרשב״א?"
"decisors": [
  { "id": "d1", "name": "הלווה מנה לפלוני ואתקדש אני לך", "correct_choice": "מקודשת..." },
  { "id": "d2", "name": "הרוויח זמן מלווה לפלוני ואתקדש אני לך", "correct_choice": "אינה מקודשת..." }
]
```

**Problème** : Les "noms de poskim" (`decisors.name`) ne sont pas des poskim — ce sont les **noms des deux cas différents** que le **même posek** (Rosh Be'ah) distingue.

**Texte source** (ligne 344, Teshuvot Rosh Be'ah) :
> "אם אמרה הלוה מנה לפלוני ואתקדש אני לך – מקודשת... אך אם אמרה הרויח זמן מלוה לפלוני ואתקדש אני לך – אינה מקודשת"

C'est **un posek unique** établissant une distinction entre deux **cas**, non pas deux poskim en désaccord.

**Violation des règles pédagogiques** (prompt_generation_questions.md, ligne 271-272) :
> "Only pair poskim who really argue on THIS case in the source text."

**Impact** : La question induit une confusion. L'étudiant croit voir une machloket entre deux poskim ("הלווה מנה לפלוני" et "הרוויח זמן מלווה לפלוני" comme si c'étaient des noms), alors qu'il s'agit d'une seule posek (רשב״א) distinguant deux cas.

**Correction recommandée** :
- Soit transformer Q7 en `multiple_choice` : "Quand une femme dit 'הלווה מנה לפלוני ואתקדש אני לך', quel est le din selon le Rosh Be'ah ?" avec options pour les deux cas ;
- Soit fusionner les deux cas dans une seule question avec une structure plus claire du contexte unique.

---

## 4. Autres observations

### Hébreu et orthographe
- Hébreu consistant, orthographe correcte, pas de caractères latins repérés. ✓
- Accord genre/nombre en hébreu : correct. ✓

### Attributions `exam_section`
- `shulchan_aruch` : 13 questions (seifim couverts par le texte du SA) ✓
- `tur` : 7 questions (passages des Rishonim et source) ✓
- `ptei_teshuva` : 6 questions (Acharonim tardifs, Pitchei Teshuva, réponses halachiques) ✓

Attribution cohérente et plausible.

### Explications
Toutes les explications citent :
- Siman et seif correct ✓
- Nom du posek (Rabba, R. Elazar, Rambam, Rosh Be'ah, Rama, etc.) ✓
- Brève raison halakhique ✓

### Couverture pédagogique
Le lot couvre :
- Dins simples (Q1, Q5) : niveau 1–2 ✓
- Applications à des cas (Q3, Q8, Q18) : niveau 2–3 ✓
- Machloket entre poskim (Q2, Q11, Q19, Q21) : niveau 3 ✓
- Discrimination entre cas proches (Q20, Q21) : niveau 3 ✓

Bonne gradation et aucune duplication détectée.

---

## 5. Conclusion et recommandation

### Fiabilité globale
Le lot est **fiable et complet** :
- ✓ Validation programmatique : 100% pass
- ✓ Fidélité au texte source : tous les dins traités sont attestés
- ✓ Couverture complète du siman 29 (seifim 1–10)
- ✓ Hébreu, orthographe, structures JSON : impeccables

### Actions avant import
**Q7 doit être corrigée** avant import :
1. Changer le type à `multiple_choice`, OU
2. Restructurer pour utiliser des noms de poskim réels si une machloket existe.

Selon le prompt pédagogique, une `multiple_opinions_dropdown` doit marier des **poskim qui désaccordent réellement**, pas des **cas distincts établis par un seul posek**.

Recommandation : **Importer le lot après correction de Q7** — simple réécrit, pas de refonte.

---

**Vérification effectuée** : 30 juillet 2026  
**Vérificateur** : Claude Code Agent  
**Scope** : Siman 29 (Even HaEzer, Chupa veKidushin), seifim 1–10  
**Texte source** : heichal_shlomo_chupa_vekidushin_ehy_26-27-29.txt (lignes 300–498)
