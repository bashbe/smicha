"""One-off data migration : remplace le subject générique ("בשר בחלב") des
questions existantes du siman פז (87, parcours bassar_bechalav) par un sujet
spécifique par seif, dérivé de שו"ת היכל שלמה (Livre 18 juin 2026.pdf).

Les seifim sont regroupés exactement comme dans la source (סעיפים א–ב,
סעיף ג, סעיף ד, סעיפים ו-ח, סעיף ט, סעיף י, סעיפים י-יא) — un même sujet est
donc partagé par plusieurs seifim quand la source elle-même ne les distingue
pas plus finement.

Le seif 5 n'a aucun contenu identifiable dans le document fourni (aucune
mention "סעיף ה" nulle part dans le texte) : les questions de ce seif sont
laissées inchangées et un avertissement est affiché. Corriger SEIF_SUBJECTS
ci-dessous puis relancer le script si une source pour le seif 5 est trouvée.

Usage :
    python -m scripts.assign_heichal_shlomo_subjects           # aperçu (dry-run)
    python -m scripts.assign_heichal_shlomo_subjects --apply   # applique les changements
    python -m scripts.assign_heichal_shlomo_subjects --apply --parcours bassar_bechalav --siman 87
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import Question, db  # noqa: E402

# seif → sujet, dérivé de שו"ת היכל שלמה סימן פז (Livre 18 juin 2026.pdf)
SEIF_SUBJECTS = {
    # סעיפים א–ב : gדר האיסור (תורה/דרבנן/מראית עין) וגדר "בישול" (מליחה/כבישה,
    # בישול אחר בישול, חיה ועוף)
    1: 'באיזה בשר נוהג איסור בישול בשר בחלב, וגדר "בישול"',
    2: 'באיזה בשר נוהג איסור בישול בשר בחלב, וגדר "בישול"',
    # סעיף ג : בשר/חלב מבהמה טמאה, בשר נבילה וטריפה, דגים וחגבים בחלב
    3: "בשר או חלב מבהמה טמאה, בשר נבילה, ודגים בחלב",
    # סעיף ד : כללי איסור מראית עין (חלב אשה, חלב שקדים, תחליפי חלב)
    4: "כללי איסור מראית עין בבשר בחלב",
    # סעיף ה : אין מקור בטקסט שסופק — לא מעודכן (ראה האזהרה בהרצה)
    # סעיפים ו-ח : דם ואיברים (עור/עצמות/שליא) בחלב, חלב זכר/מתה/מעושן
    6: "בישול דם ואיברים בחלב; חלב זכר, מתה ומעושן",
    7: "בישול דם ואיברים בחלב; חלב זכר, מתה ומעושן",
    8: "בישול דם ואיברים בחלב; חלב זכר, מתה ומעושן",
    # סעיף ט : חלב הנמצא בקיבת הבהמה
    9: "חלב הנמצא בקיבת הבהמה",
    # סעיף י : ייבוש עור קיבה/בשר והשריה בחלב + מעמיד מחלב קיבה שקיבל טעם בשר
    10: "ייבוש עור קיבה ובשר; העמדת גבינה בחלב קיבה שקיבל טעם בשר",
    # סעיפים י-יא : מעמיד מעור קיבה כשרה/טמאה, וזה וזה גורם
    11: "העמדת גבינה בעור קיבה כשרה או טמאה, וזה וזה גורם",
}


def run(parcours: str, siman: int, apply: bool) -> None:
    app = create_app()
    with app.app_context():
        seifim_present = {
            row[0]
            for row in db.session.query(Question.seif)
            .filter_by(parcours=parcours, siman=siman)
            .distinct()
        }
        missing = sorted(s for s in seifim_present if s not in SEIF_SUBJECTS)

        total = 0
        for seif, subject in sorted(SEIF_SUBJECTS.items()):
            query = Question.query.filter_by(parcours=parcours, siman=siman, seif=seif)
            count = query.count()
            if count == 0:
                continue
            total += count
            print(f"seif {seif:>2} ({count:>3} שאלות) → {subject}")
            if apply:
                query.update({"subject": subject})

        if missing:
            print(
                f"\nאזהרה: לא נמצא מיפוי עבור seif {missing} — "
                "שאלות אלו לא עודכנו (ראה SEIF_SUBJECTS בקובץ זה)."
            )

        if apply:
            db.session.commit()
            print(f"\n{total} שאלות עודכנו.")
        else:
            print(f"\n{total} שאלות ישונו (dry-run — הרץ עם --apply כדי לשמור).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parcours", default="bassar_bechalav")
    parser.add_argument("--siman", type=int, default=87)
    parser.add_argument("--apply", action="store_true", help="שמור בפועל (ברירת מחדל: aperçu בלבד)")
    args = parser.parse_args()
    run(args.parcours, args.siman, args.apply)
