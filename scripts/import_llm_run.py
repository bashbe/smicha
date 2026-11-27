"""Import an /llm-pipeline run directory into the database.

Reads `docs/pipeline_runs/<run_id>/` produced by the `.claude/commands/llm-pipeline.md`
skill and:

1. creates the `LLMPipelineRun` row (status `done` if meta says so);
2. imports `final_questions.json` into `questions` (status `pending`, or
   `a_revoir` when the question carries `_llm_status: "llm_flagged"`) via the
   real validator `question_types.normalize_imported_question` — invalid
   questions are skipped and reported;
3. imports every `*_reviews_v*.json` into `llm_reviews` (final iteration
   reviews get their `question_id` resolved against the imported questions;
   earlier iterations keep `question_id=NULL` for traceability);
4. imports every `*_coherence_v*.json` into `llm_coherence_reports`.

Usage:

    python -m scripts.import_llm_run --run-id ehy_26_20260731-143000
    python -m scripts.import_llm_run --run-dir docs/pipeline_runs/ehy_26_20260731-143000
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import LLMCoherenceReport, LLMPipelineRun, LLMReview, Question, db  # noqa: E402
from question_types import normalize_imported_question  # noqa: E402
from subjects import get_or_create_subject  # noqa: E402
from tags import sync_question_hidden_tags  # noqa: E402

RUNS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "pipeline_runs")

REVIEW_RE = re.compile(r"^(\d+)_reviews_v(\d+)\.json$")
COHERENCE_RE = re.compile(r"^(\d+)_coherence_v(\d+)\.json$")


def _load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _iteration_from_name(name: str, pattern: re.Pattern) -> int | None:
    m = pattern.match(name)
    return int(m.group(2)) - 1 if m else None  # v1 -> iteration 0


def import_run(run_dir: str, app=None) -> dict:
    if app is None:
        app = create_app()
        ctx = app.app_context()
        ctx.push()
        try:
            return _import_run_in_ctx(run_dir)
        finally:
            ctx.pop()
    return _import_run_in_ctx(run_dir)


def _import_run_in_ctx(run_dir: str) -> dict:
    meta = _load_json(os.path.join(run_dir, "meta.json"))
    run_id = os.path.basename(os.path.normpath(run_dir))

    existing = LLMPipelineRun.query.get(run_id)
    if existing:
        print(f"Run {run_id} already imported (status={existing.status}) — aborting (idempotent).")
        return {"run_id": run_id, "already_imported": True}

    final_questions_path = os.path.join(run_dir, "final_questions.json")
    if not os.path.exists(final_questions_path):
        raise SystemExit(f"No final_questions.json in {run_dir} — run not finished?")
    final_questions = _load_json(final_questions_path)

    run = LLMPipelineRun(
        id=run_id,
        siman=int(meta["siman"]),
        chelek=meta.get("chelek"),
        parcours=meta["parcours"],
        status="done" if meta.get("status") == "done" else "running",
        iterations=int(meta.get("iterations", 0)),
        max_iterations=int(meta.get("max_iter", 3)),
        run_dir=os.path.relpath(run_dir, os.path.dirname(RUNS_ROOT)),
        total_questions=len(final_questions),
        llm_approved=sum(1 for q in final_questions if q.get("_llm_status") != "llm_flagged"),
        llm_flagged=sum(1 for q in final_questions if q.get("_llm_status") == "llm_flagged"),
        finished_at=datetime.utcnow() if meta.get("status") == "done" else None,
    )
    db.session.add(run)
    db.session.flush()

    imported_index_to_qid: dict[int, str] = {}
    inserted = failed = 0
    for idx, raw in enumerate(final_questions):
        flagged = raw.pop("_llm_status", None) == "llm_flagged"
        norm = normalize_imported_question(raw)
        if not norm.get("valid"):
            failed += 1
            print(f"  SKIP Q{idx}: {norm.get('issue')}")
            continue
        ins = norm["insert"]
        subj = get_or_create_subject(ins.get("parcours"), ins.get("siman"), ins.get("subject"))
        question = Question(
            question_type=ins["question_type"],
            text=ins["text"],
            payload=ins["payload"],
            choices=ins["choices"],
            correct_answer=ins["correct_answer"],
            explanation=ins["explanation"],
            difficulty=ins["difficulty"],
            section=ins["section"],
            source_ref=ins["source_ref"],
            subject_id=subj.id,
            siman=ins.get("siman"),
            seif=ins.get("seif"),
            parcours=ins.get("parcours"),
            status="a_revoir" if flagged else "pending",
        )
        sync_question_hidden_tags(question, ins.get("parcours"), ins["tags"])
        db.session.add(question)
        db.session.flush()
        imported_index_to_qid[idx] = question.id
        inserted += 1

    reviews_count = 0
    for name in sorted(os.listdir(run_dir)):
        path = os.path.join(run_dir, name)
        m = REVIEW_RE.match(name)
        if m:
            iteration = int(m.group(2)) - 1
            data = _load_json(path)
            is_final = name == "final_reviews.json"
            for r in data.get("reviews", []):
                q_idx = int(r["question_index"])
                qid = imported_index_to_qid.get(q_idx) if is_final else None
                db.session.add(LLMReview(
                    run_id=run_id,
                    question_index=q_idx,
                    question_id=qid,
                    agent_name=r["agent"],
                    agent_label=r.get("label", r["agent"]),
                    vote=r["vote"],
                    confidence=r.get("confidence"),
                    comment=r.get("comment"),
                    raw_response=r,
                    iteration=iteration,
                ))
                reviews_count += 1
            continue
        m = COHERENCE_RE.match(name)
        if m:
            iteration = int(m.group(2)) - 1
            data = _load_json(path)
            db.session.add(LLMCoherenceReport(run_id=run_id, iteration=iteration, report_json=data))
        if name == "final_reviews.json":
            data = _load_json(path)
            for r in data.get("reviews", []):
                q_idx = int(r["question_index"])
                db.session.add(LLMReview(
                    run_id=run_id,
                    question_index=q_idx,
                    question_id=imported_index_to_qid.get(q_idx),
                    agent_name=r["agent"],
                    agent_label=r.get("label", r["agent"]),
                    vote=r["vote"],
                    confidence=r.get("confidence"),
                    comment=r.get("comment"),
                    raw_response=r,
                    iteration=int(data.get("iteration", 0)),
                ))
                reviews_count += 1

    db.session.commit()
    summary = {
        "run_id": run_id,
        "questions_inserted": inserted,
        "questions_failed": failed,
        "reviews_imported": reviews_count,
        "llm_approved": run.llm_approved,
        "llm_flagged": run.llm_flagged,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an /llm-pipeline run into the DB")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-id", help="run id (directory name under docs/pipeline_runs/)")
    g.add_argument("--run-dir", help="full or relative path to the run directory")
    args = parser.parse_args()
    run_dir = args.run_dir or os.path.join(RUNS_ROOT, args.run_id)
    if not os.path.isdir(run_dir):
        raise SystemExit(f"Run directory not found: {run_dir}")
    import_run(run_dir)


if __name__ == "__main__":
    main()
