"""One-off data migration : remplace le subject générique ("בשר בחלב") des
questions existantes du siman פז (87, parcours bassar_bechalav) par un sujet
spécifique par seif, dérivé de שו"ת היכל שלמה (Livre 18 juin 2026.pdf).

Les seifim sont regroupés exactement comme dans la source (סעיפים א–ב,
סעיף ג, סעיף ד, סעיפים ו-ח, סעיף ט, סעיף י, סעיפים י-יא) — un même sujet est
donc partagé par plusieurs seifim quand la source elle-même ne les distingue
pas plus finement.

Le seif 5 n'a aucun contenu identifiable dans le document fourni (aucune
mention "סעיף ה" nulle part dans le texte) ; son sujet a été communiqué
directement par l'utilisateur (ביצה בתוך התרנגולת).

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

# seif → sujet (quelques mots max), dérivé de שו"ת היכל שלמה סימן פז
# (Livre 18 juin 2026.pdf)
SEIF_SUBJECTS = {
    # סעיפים א–ב : גדר האיסור (תורה/דרבנן/מראית עין) וגדר "בישול" (מליחה/כבישה,
    # בישול אחר בישול, חיה ועוף)
    1: "גדר בישול בבשר בחלב",
    2: "גדר בישול בבשר בחלב",
    # סעיף ג : בשר/חלב מבהמה טמאה, בשר נבילה וטריפה, דגים וחגבים בחלב
    3: "בשר וחלב מבהמה טמאה",
    # סעיף ד : כללי איסור מראית עין (חלב אשה, חלב שקדים, תחליפי חלב)
    4: "איסור מראית עין בבב״ח",
    # סעיף ה : אין מקור בטקסט שסופק — נמסר ישירות ע"י המשתמש
    5: "ביצה בתוך התרנגולת כבשר",
    # סעיפים ו-ח : דם ואיברים (עור/עצמות/שליא) בחלב, חלב זכר/מתה/מעושן
    6: "דם ואיברים מבושלים בחלב",
    7: "דם ואיברים מבושלים בחלב",
    8: "דם ואיברים מבושלים בחלב",
    # סעיף ט : חלב הנמצא בקיבת הבהמה
    9: "חלב בתוך קיבת הבהמה",
    # סעיף י : ייבוש עור קיבה/בשר והשריה בחלב + מעמיד מחלב קיבה שקיבל טעם בשר
    10: "ייבוש בשר ועור קיבה",
    # סעיפים י-יא : מעמיד מעור קיבה כשרה/טמאה, וזה וזה גורם
    11: "העמדת גבינה בעור קיבה",
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
