"""Strict question-schema normalization shared by importer, validator, and player.

Port of src/lib/question-types.ts.
"""

from __future__ import annotations

import json
import re

QUESTION_TYPES = [
    "multiple_choice",
    "multiple_opinions_dropdown",
    "practical_scenario",
    "true_false",
]

VALID_SECTIONS = ("shulchan_aruch", "tur", "tur_shulchan_aruch", "psikei_admur", "ptei_teshuva")
VALID_PARCOURS = ("bassar_bechalav",)

HEBREW_RE = re.compile(r"[֐-׿]")
LATIN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")


def _normalize_sections(value) -> list[str]:
    """Accept a string or list, always return a non-empty list of valid sections."""
    if isinstance(value, str) and value:
        sections = [value]
    elif isinstance(value, list):
        sections = [str(s).strip() for s in value if str(s).strip()]
    else:
        sections = []
    valid = [s for s in sections if s in VALID_SECTIONS]
    return valid if valid else ["shulchan_aruch"]



def _text(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def _add_text_issue(issues: list, value, label: str) -> None:
    s = _text(value)
    if not s:
        issues.append(f"{label} חסר")
    elif not HEBREW_RE.search(s) or LATIN_RE.search(s):
        issues.append(f"{label} חייב להיות בעברית בלבד")


def _has_hebrew_key(obj) -> bool:
    if not isinstance(obj, (dict, list)):
        return False
    if isinstance(obj, list):
        return any(_has_hebrew_key(v) for v in obj)
    return any(HEBREW_RE.search(str(key)) or _has_hebrew_key(value) for key, value in obj.items())


def _source_to_ref(q) -> str | None:
    src = q.get("source")
    if isinstance(src, dict):
        return json.dumps(src, ensure_ascii=False)
    return str(q["id"]) if q.get("id") else None


def _normalize_tags(tags) -> list:
    if isinstance(tags, list):
        return [str(t).strip() for t in tags if str(t).strip()]
    return []


def _validate_common(q, issues: list):
    if not isinstance(q, dict):
        issues.append("השאלה חייבת להיות אובייקט JSON")
        return None
    if _has_hebrew_key(q):
        issues.append("שמות השדות חייבים להיות באנגלית")
    qtype = q.get("type")
    if qtype not in QUESTION_TYPES:
        issues.append("סוג שאלה לא נתמך")
        return None
    if q.get("difficulty_level") not in (1, 2, 3):
        issues.append("difficulty_level חייב להיות מספר בין 1 ל-3")
    raw_section = q.get("exam_section")
    sections = _normalize_sections(raw_section)
    if not sections or any(s not in VALID_SECTIONS for s in sections):
        issues.append("exam_section לא תקין")
    _add_text_issue(issues, q.get("explanation"), "הסבר")
    # Mandatory metadata fields
    if q.get("parcours") not in VALID_PARCOURS:
        issues.append(f"parcours חייב להיות: {', '.join(VALID_PARCOURS)}")
    _add_text_issue(issues, q.get("sujet"), "sujet")
    siman = q.get("siman")
    if not isinstance(siman, int) or isinstance(siman, bool) or siman <= 0:
        issues.append("siman חייב להיות מספר שלם חיובי")
    seif = q.get("seif")
    if not isinstance(seif, int) or isinstance(seif, bool) or seif <= 0:
        issues.append("seif חייב להיות מספר שלם חיובי")
    return qtype


def _validate_numbered_options(q, issues: list) -> None:
    options = q.get("options") if isinstance(q.get("options"), list) else []
    if len(options) != 4:
        issues.append("חייבות להיות בדיוק 4 תשובות")
    numbers = [o.get("number") if isinstance(o, dict) else None for o in options]
    unique_numbers = set(numbers)
    if len(unique_numbers) != len(options) or not all(n in unique_numbers for n in (1, 2, 3, 4)):
        issues.append("מספרי התשובות חייבים להיות 1, 2, 3, 4 ללא כפילות")
    for index, option in enumerate(options):
        option = option if isinstance(option, dict) else {}
        _add_text_issue(issues, option.get("text"), f"תשובה {index + 1}")
        if "is_correct" in option and not isinstance(option.get("is_correct"), bool):
            issues.append(f"is_correct בתשובה {index + 1} חייב להיות boolean")
    correct = [o for o in options if isinstance(o, dict) and o.get("is_correct") is True]
    if len(correct) == 0:
        issues.append("No correct answer marked (is_correct: true)")
    if len(correct) > 1:
        issues.append("יש יותר מתשובה נכונה אחת")


def normalize_imported_question(q) -> dict:
    """Returns {raw, valid, issue?, insert?}."""
    try:
        issues: list = []
        qtype = _validate_common(q, issues)
        if not qtype:
            return {"raw": q, "valid": False, "issue": " · ".join(issues)}

        if qtype == "multiple_choice":
            _add_text_issue(issues, q.get("question_text"), "טקסט השאלה")
            _validate_numbered_options(q, issues)

        if qtype == "practical_scenario":
            _add_text_issue(issues, q.get("scenario_text"), "תיאור המקרה")
            _add_text_issue(issues, q.get("question_text"), "טקסט השאלה")
            _validate_numbered_options(q, issues)

        if qtype == "multiple_opinions_dropdown":
            _add_text_issue(issues, q.get("question_text"), "טקסט השאלה")
            dropdown_choices = q.get("dropdown_choices") if isinstance(q.get("dropdown_choices"), list) else []
            if len(dropdown_choices) < 2:
                issues.append("dropdown_choices חייב להכיל לפחות 2 אפשרויות")
            for index, choice in enumerate(dropdown_choices):
                _add_text_issue(issues, choice, f"אפשרות dropdown {index + 1}")
            decisors = q.get("decisors") if isinstance(q.get("decisors"), list) else []
            if len(decisors) < 2:
                issues.append("חייבים לפחות 2 פוסקים")
            for index, decisor in enumerate(decisors):
                decisor = decisor if isinstance(decisor, dict) else {}
                if not _text(decisor.get("id")):
                    issues.append(f"חסר id לפוסק {index + 1}")
                _add_text_issue(issues, decisor.get("name"), f"שם פוסק {index + 1}")
                _add_text_issue(issues, decisor.get("correct_choice"), f"תשובת פוסק {index + 1}")
                if "is_correct" in decisor:
                    issues.append("אין להשתמש ב-is_correct בפורמט דעות")
                if _text(decisor.get("correct_choice")) and decisor.get("correct_choice") not in dropdown_choices:
                    issues.append(f"correct_choice של {decisor.get('name') or index + 1} אינו מופיע ברשימת הבחירות")
            distinct = {d.get("correct_choice") for d in decisors if isinstance(d, dict) and d.get("correct_choice")}
            if len(decisors) >= 2 and len(distinct) < 2:
                issues.append("חייב להיות disagreement אמיתי בין הפוסקים")

        if qtype == "true_false":
            _add_text_issue(issues, q.get("statement_text"), "טקסט ההצהרה")
            if not isinstance(q.get("correct_answer"), bool):
                issues.append("correct_answer חייב להיות boolean")
            if "is_correct" in q:
                issues.append("אין להשתמש ב-is_correct בפורמט נכון/לא נכון")

        if issues:
            return {"raw": q, "valid": False, "issue": " · ".join(issues)}

        difficulty = q["difficulty_level"]
        section = _normalize_sections(q.get("exam_section"))
        tags = _normalize_tags(q.get("tags"))
        explanation = _text(q.get("explanation"))

        if qtype in ("multiple_choice", "practical_scenario"):
            prompt = _text(q.get("question_text"))
            correct = next(o for o in q["options"] if o.get("is_correct") is True)
            correct_answer = str(correct["number"])
            choices = [{"label": str(o["number"]), "text": _text(o.get("text"))} for o in q["options"]]
        elif qtype == "multiple_opinions_dropdown":
            prompt = _text(q.get("question_text"))
            answer_map = {str(d["id"]): _text(d.get("correct_choice")) for d in q["decisors"]}
            correct_answer = json.dumps(answer_map, ensure_ascii=False)
            choices = [{"label": _text(c), "text": _text(c)} for c in q["dropdown_choices"]]
        else:  # true_false
            prompt = _text(q.get("statement_text"))
            correct_answer = "true" if q.get("correct_answer") else "false"
            choices = [{"label": "true", "text": "נכון"}, {"label": "false", "text": "לא נכון"}]

        return {
            "raw": q,
            "valid": True,
            "insert": {
                "question_type": qtype,
                "text": prompt,
                "explanation": explanation,
                "difficulty": difficulty,
                "section": section,
                "payload": q,
                "correct_answer": correct_answer,
                "choices": choices,
                "source_ref": _source_to_ref(q),
                "tags": tags,
                "parcours": q.get("parcours"),
                "subject": _text(q.get("sujet")),
                "siman": int(q["siman"]),
                "seif": int(q["seif"]),
            },
        }
    except Exception as e:  # noqa: BLE001
        return {"raw": q, "valid": False, "issue": str(e) or "שגיאה לא ידועה"}


def build_payload_from_draft(row: dict) -> dict:
    payload = dict(row.get("payload") or {})
    payload["type"] = row.get("question_type") or payload.get("type")
    payload["difficulty_level"] = int(row.get("difficulty") or payload.get("difficulty_level") or 2)
    payload["exam_section"] = _normalize_sections(row.get("section") or payload.get("exam_section"))
    payload["explanation"] = row.get("explanation") or payload.get("explanation") or ""
    payload["parcours"] = (row.get("parcours") or payload.get("parcours") or "").strip()
    payload["sujet"] = (row.get("subject") or payload.get("sujet") or "").strip()
    siman_val = row.get("siman") if row.get("siman") is not None else payload.get("siman")
    try:
        payload["siman"] = int(siman_val) if siman_val not in (None, "") else 0
    except (ValueError, TypeError):
        payload["siman"] = 0
    seif_val = row.get("seif") if row.get("seif") is not None else payload.get("seif")
    try:
        payload["seif"] = int(seif_val) if seif_val not in (None, "") else 0
    except (ValueError, TypeError):
        payload["seif"] = 0
    if isinstance(row.get("tags"), list):
        payload["tags"] = row["tags"]
    elif isinstance(payload.get("tags"), list):
        pass
    else:
        payload["tags"] = []
    return payload


def sync_question_row_from_payload(row: dict) -> dict:
    """Returns {row, error}."""
    payload = build_payload_from_draft(row)
    normalized = normalize_imported_question(payload)
    if not normalized.get("valid") or not normalized.get("insert"):
        merged = dict(row)
        merged["payload"] = payload
        return {"row": merged, "error": normalized.get("issue") or "שאלה לא תקינה"}
    ins = normalized["insert"]
    merged = dict(row)
    merged.update(
        question_type=ins["question_type"],
        text=ins["text"],
        explanation=ins["explanation"],
        difficulty=ins["difficulty"],
        section=ins["section"],
        payload=ins["payload"],
        choices=ins["choices"],
        correct_answer=ins["correct_answer"],
        source_ref=ins["source_ref"],
        tags=ins["tags"],
        parcours=ins["parcours"],
        subject=ins["subject"],
        siman=ins["siman"],
        seif=ins["seif"],
    )
    return {"row": merged, "error": None}


def normalize_db_question(row: dict) -> dict:
    """Normalize a stored question row into a player-friendly dict."""
    qtype = row.get("question_type") or "multiple_choice"
    payload = row.get("payload") or {}
    explanation = row.get("explanation") or payload.get("explanation")

    if qtype == "true_false":
        return {
            "type": qtype,
            "prompt": _text(payload.get("statement_text")) or row.get("text") or "",
            "scenario": None,
            "choices": [
                {"key": "true", "label": "✓", "text": "נכון"},
                {"key": "false", "label": "✗", "text": "לא נכון"},
            ],
            "correctKey": "true" if payload.get("correct_answer") is True else "false",
            "explanation": explanation,
        }

    if qtype == "multiple_opinions_dropdown":
        dropdown_choices = (
            [_text(c) for c in payload.get("dropdown_choices", []) if _text(c)]
            if isinstance(payload.get("dropdown_choices"), list)
            else []
        )
        decisors = payload.get("decisors") if isinstance(payload.get("decisors"), list) else []
        normalized_decisors = [
            {"id": str(d.get("id")), "name": _text(d.get("name")), "correctChoice": _text(d.get("correct_choice"))}
            for d in decisors
        ]
        correct_key = row.get("correct_answer") or json.dumps(
            {d["id"]: d["correctChoice"] for d in normalized_decisors}, ensure_ascii=False
        )
        return {
            "type": qtype,
            "prompt": _text(payload.get("question_text")) or row.get("text") or "",
            "scenario": None,
            "choices": [],
            "correctKey": correct_key,
            "dropdownChoices": dropdown_choices,
            "decisors": normalized_decisors,
            "explanation": explanation,
        }

    opts = payload.get("options") if isinstance(payload.get("options"), list) else []
    correct_opt = next((o for o in opts if o.get("is_correct") is True), None)
    return {
        "type": qtype,
        "prompt": _text(payload.get("question_text")) or row.get("text") or "",
        "scenario": _text(payload.get("scenario_text")) if qtype == "practical_scenario" else None,
        "choices": [{"key": str(o["number"]), "label": str(o["number"]), "text": _text(o.get("text"))} for o in opts],
        "correctKey": str(correct_opt["number"]) if correct_opt else str(row.get("correct_answer") or ""),
        "explanation": explanation,
    }


def is_correct_answer(question: dict, key: str) -> bool:
    if question["type"] != "multiple_opinions_dropdown":
        return question["correctKey"] == key
    try:
        given = json.loads(key)
        if not isinstance(given, dict):
            given = {}
    except (ValueError, TypeError):
        given = {}
    return all(given.get(d["id"]) == d["correctChoice"] for d in question.get("decisors", []))
