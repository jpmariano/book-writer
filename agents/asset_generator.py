import json
import re
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb
from langchain_ollama import ChatOllama

from state.book_state import BookState
from agents.writer import decide_image_need


POSTGRES_URL = "postgresql://book_writer:book_writer_dev_password@localhost:5432/book_writer"

llm = ChatOllama(model="qwen3:8b", temperature=0.4)


def extract_code_samples(content: str) -> list[dict]:
    match = re.search(r"\[\s*{.*?}\s*\]|\[\s*\]", content, re.DOTALL)
    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def get_approved_drafts(book_id: str, research_run_id: str):
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    chapter_title,
                    topic_title,
                    general_explanation,
                    technical_explanation
                FROM drafts
                WHERE book_id = %s
                  AND research_run_id = %s
                  AND draft_status = 'approved'
                  AND review_status = 'passed'
                """,
                (book_id, research_run_id),
            )
            return cur.fetchall()


def generate_code_samples(chapter_title, topic_title, general_explanation, technical_explanation):
    prompt = f"""
You are generating optional code samples for an already approved book draft.

Only create code if it genuinely helps the topic.
If code is not useful, return [].

Chapter:
{chapter_title}

Topic:
{topic_title}

Approved draft:
GENERAL_EXPLANATION:
{general_explanation}

TECHNICAL_EXPLANATION:
{technical_explanation}

Return only valid JSON:

[
  {{
    "title": "...",
    "language": "...",
    "purpose": "...",
    "code": "..."
  }}
]

Or:

[]
""".strip()

    response = llm.invoke(prompt)
    return extract_code_samples(response.content)


def update_assets(draft_id: str, code_samples: list[dict], image: dict | None):
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE drafts
                SET
                    code_samples = %s,
                    image = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    Jsonb(code_samples or []),
                    Jsonb(image) if image else None,
                    datetime.now(timezone.utc),
                    draft_id,
                ),
            )


def asset_generator(state: BookState):
    print("Asset Generator started")

    book_id = state["book_id"]
    research_run_id = state["research_run_id"]

    book_title = state.get("book_title", "Untitled Book")
    book_subject = state.get("book_subject")
    genre = state.get("genre")
    audience = state.get("audience", [])

    drafts = get_approved_drafts(book_id, research_run_id)

    for row in drafts:
        (
            draft_id,
            chapter_title,
            topic_title,
            general_explanation,
            technical_explanation,
        ) = row

        explanations = {
            "general_explanation": general_explanation,
            "technical_explanation": technical_explanation,
            "code_samples": [],
        }

        code_samples = generate_code_samples(
            chapter_title=chapter_title,
            topic_title=topic_title,
            general_explanation=general_explanation,
            technical_explanation=technical_explanation,
        )

        explanations["code_samples"] = code_samples

        image = decide_image_need(
            topic_title=topic_title,
            chapter_title=chapter_title,
            explanations=explanations,
            book_title=book_title,
            book_subject=book_subject,
            genre=genre,
            audience=audience,
        )

        update_assets(
            draft_id=draft_id,
            code_samples=code_samples,
            image=image,
        )

    print("Asset Generator done")

    return {
        "asset_generated_draft_count": len(drafts),
    }