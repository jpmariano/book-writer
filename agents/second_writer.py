import json
import re
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb
from langchain_ollama import ChatOllama

from state.book_state import BookState


POSTGRES_URL = "postgresql://book_writer:book_writer_dev_password@localhost:5432/book_writer"

# A little lower temperature than the first writer: this is an editor/reviser.
llm = ChatOllama(model="qwen3:8b", temperature=0.6)


def extract_code_samples(content: str) -> list[dict]:
    if "CODE_SAMPLES:" not in content:
        return []

    raw = content.split("CODE_SAMPLES:", 1)[1].strip()
    match = re.search(r"\[\s*{.*?}\s*\]|\[\s*\]", raw, re.DOTALL)

    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def parse_revised_content(content: str, fallback_code_samples: list[dict]) -> dict:
    code_samples = extract_code_samples(content)

    if not code_samples:
        code_samples = fallback_code_samples or []

    if "TECHNICAL_EXPLANATION:" in content:
        before, technical = content.split("TECHNICAL_EXPLANATION:", 1)
        general = before.replace("GENERAL_EXPLANATION:", "").strip()

        if "CODE_SAMPLES:" in technical:
            technical = technical.split("CODE_SAMPLES:", 1)[0].strip()
        else:
            technical = technical.strip()
    else:
        general = content.strip()
        technical = ""

    return {
        "general_explanation": general,
        "technical_explanation": technical,
        "code_samples": code_samples,
    }


def get_latest_failed_reviews(book_id: str, research_run_id: str):
    """
    Returns one latest failed review per draft, but only for drafts currently
    marked needs_revision. This prevents old failed reviews from being revised
    after a draft has already passed.
    """
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (dr.draft_id)
                    d.id,
                    d.task_id,
                    d.chapter_title,
                    d.topic_title,
                    d.general_explanation,
                    d.technical_explanation,
                    d.code_samples,
                    d.image,
                    dr.id AS review_id,
                    dr.review_status,
                    dr.plagiarism_score,
                    dr.review_notes
                FROM draft_reviews dr
                JOIN drafts d
                    ON d.id = dr.draft_id
                WHERE dr.book_id = %s
                  AND dr.research_run_id = %s
                  AND dr.review_status = 'failed'
                  AND d.draft_status = 'needs_revision'
                ORDER BY dr.draft_id, dr.created_at DESC
                """,
                (book_id, research_run_id),
            )
            return cur.fetchall()


def revise_draft(
    chapter_title: str,
    topic_title: str,
    general_explanation: str,
    technical_explanation: str,
    code_samples: list[dict],
    review_status: str,
    plagiarism_score: float,
    review_notes: str,
) -> dict:
    prompt = f"""
You are the Second Writer Agent for a technical book.

Your job is to revise a draft that failed review. Use the review notes as the source of truth
for what must be fixed.

Chapter:
{chapter_title}

Topic:
{topic_title}

Latest review status:
{review_status}

Latest plagiarism score:
{plagiarism_score}

Latest review notes:
{review_notes}

Current draft:

GENERAL_EXPLANATION:
{general_explanation}

TECHNICAL_EXPLANATION:
{technical_explanation}

CODE_SAMPLES:
{json.dumps(code_samples or [], ensure_ascii=False, indent=2)}

Revision requirements:
- Fix every issue mentioned in the latest review notes.
- If plagiarism or similarity is high, rewrite the structure and wording substantially.
- Do not copy source wording.
- Keep only technically accurate claims.
- Make the explanation clearer, more complete, and more useful for software engineers and AI engineers.
- Preserve correct code samples, but rewrite or replace weak code samples when needed.
- Do not mention the review process to the reader.

Return exactly this format:

GENERAL_EXPLANATION:
...

TECHNICAL_EXPLANATION:
...

CODE_SAMPLES:
[
  {{
    "title": "...",
    "language": "...",
    "purpose": "...",
    "code": "..."
  }}
]

If no code is needed:

CODE_SAMPLES:
[]
"""

    response = llm.invoke(prompt)
    return parse_revised_content(response.content, fallback_code_samples=code_samples)


def update_draft_after_revision(
    draft_id: str,
    general_explanation: str,
    technical_explanation: str,
    code_samples: list[dict],
):
    """
    Reset review_status to pending so plagiarism_checker can review this
    updated version again.
    """
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE drafts
                SET
                    general_explanation = %s,
                    technical_explanation = %s,
                    code_samples = %s,
                    draft_status = 'revised',
                    review_status = 'pending',
                    plagiarism_score = NULL,
                    review_notes = NULL,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    general_explanation,
                    technical_explanation,
                    Jsonb(code_samples or []),
                    datetime.now(timezone.utc),
                    draft_id,
                ),
            )


def second_writer(state: BookState):
    print("Second Writer / Revision Writer started")

    book_id = state["book_id"]
    research_run_id = state["research_run_id"]

    max_revision_rounds = state.get("max_revision_rounds", 3)
    revision_round = state.get("revision_round", 0)
    print(f"revision_round: {revision_round}")
    if revision_round >= max_revision_rounds:
        print("Maximum revision rounds reached; stopping revisions.")
        return {
            "revised_draft_count": 0,
            "revision_round": revision_round,
            "stop_revisions": True,
        }

    failed_reviews = get_latest_failed_reviews(book_id, research_run_id)

    revised_count = 0
    revised_draft_ids = []

    for row in failed_reviews:
        (
            draft_id,
            task_id,
            chapter_title,
            topic_title,
            general_explanation,
            technical_explanation,
            code_samples,
            image,
            review_id,
            review_status,
            plagiarism_score,
            review_notes,
        ) = row

        print(f"Revising topic: {topic_title}")

        revised = revise_draft(
            chapter_title=chapter_title,
            topic_title=topic_title,
            general_explanation=general_explanation,
            technical_explanation=technical_explanation,
            code_samples=code_samples or [],
            review_status=review_status,
            plagiarism_score=plagiarism_score,
            review_notes=review_notes,
        )

        update_draft_after_revision(
            draft_id=draft_id,
            general_explanation=revised["general_explanation"],
            technical_explanation=revised["technical_explanation"],
            code_samples=revised["code_samples"],
        )

        revised_count += 1
        revised_draft_ids.append(draft_id)

    print("Second Writer done")

    return {
        "revised_draft_count": revised_count,
        "revised_draft_ids": revised_draft_ids,
        "revision_round": revision_round + 1,
        "stop_revisions": False,
    }
