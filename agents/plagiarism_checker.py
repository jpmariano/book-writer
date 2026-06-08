from difflib import SequenceMatcher
import uuid
from datetime import datetime, timezone
import psycopg
from langchain_ollama import ChatOllama
from state.book_state import BookState
from agents.prompt_utils import build_quality_review_prompt


POSTGRES_URL = "postgresql://book_writer:book_writer_dev_password@localhost:5432/book_writer"

llm = ChatOllama(model="deepseek-r1:latest", temperature=0.2)


def similarity_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    a = a[:5000]
    b = b[:5000]

    return SequenceMatcher(None, a, b).ratio()


def get_drafts(book_id: str, research_run_id: str):
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    task_id,
                    chapter_title,
                    topic_title,
                    general_explanation,
                    technical_explanation,
                    used_source_ids
                FROM drafts
                WHERE book_id = %s
                AND research_run_id = %s
                AND review_status = 'pending'
                """,
                (book_id, research_run_id),
            )

            return cur.fetchall()


def get_sources(source_ids: list[str]):
    if not source_ids:
        return []

    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_title, source_url, full_text
                FROM research_sources
                WHERE id = ANY(%s)
                """,
                (source_ids,),
            )

            return cur.fetchall()


def quality_review(
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience,
    chapter_title: str,
    topic_title: str,
    draft_text: str,
) -> str:
    prompt = build_quality_review_prompt(
        book_title=book_title,
        book_subject=book_subject,
        genre=genre,
        audience=audience,
        chapter_title=chapter_title,
        topic_title=topic_title,
        draft_text=draft_text,
    )

    response = llm.invoke(prompt)
    return response.content.strip()

def update_draft_review(
    draft_id: str,
    draft_status: str,
    review_status: str,
    plagiarism_score: float,
    review_notes: str,
):
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE drafts
                SET
                    draft_status = %s,
                    review_status = %s,
                    plagiarism_score = %s,
                    review_notes = %s
                WHERE id = %s
                """,
                (
                    draft_status,
                    review_status,
                    plagiarism_score,
                    review_notes,
                    draft_id,
                ),
            )


def save_draft_review(
    draft_id: str,
    book_id: str,
    research_run_id: str,
    task_id: str,
    review_type: str,
    review_status: str,
    plagiarism_score: float,
    quality_score: float | None,
    completeness_score: float | None,
    review_notes: str,
):
    review_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO draft_reviews (
                    id,
                    draft_id,
                    book_id,
                    research_run_id,
                    task_id,
                    review_type,
                    review_status,
                    plagiarism_score,
                    quality_score,
                    completeness_score,
                    review_notes,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    review_id,
                    draft_id,
                    book_id,
                    research_run_id,
                    task_id,
                    review_type,
                    review_status,
                    plagiarism_score,
                    quality_score,
                    completeness_score,
                    review_notes,
                    created_at,
                ),
            )

    return review_id

def plagiarism_checker(state: BookState):
    print("Plagiarism / Quality Checker started")

    book_id = state["book_id"]
    research_run_id = state["research_run_id"]

    book_title = state.get("book_title", "Untitled Book")
    book_subject = state.get("book_subject")
    genre = state.get("genre")
    audience = state.get("audience", [])

    drafts = get_drafts(book_id, research_run_id)

    approved_count = 0
    revision_count = 0
    checked_count = 0

    for draft in drafts:
        (
            draft_id,
            task_id,
            chapter_title,
            topic_title,
            general_explanation,
            technical_explanation,
            used_source_ids,
        ) = draft

        checked_count += 1

        draft_text = f"""
{general_explanation}

{technical_explanation}
""".strip()

        sources = get_sources(used_source_ids or [])

        max_similarity = 0.0

        for source in sources:
            source_id, source_title, source_url, full_text = source
            score = similarity_score(draft_text, full_text)
            max_similarity = max(max_similarity, score)

        review = quality_review(
            book_title=book_title,
            book_subject=book_subject,
            genre=genre,
            audience=audience,
            chapter_title=chapter_title,
            topic_title=topic_title,
            draft_text=draft_text,
        )

        plagiarism_failed = max_similarity > 0.35
        quality_failed = review.upper().startswith("NEEDS_REVISION")

        if plagiarism_failed or quality_failed:
            status = "needs_revision"
            review_status = "failed"
            revision_count += 1
        else:
            status = "approved"
            review_status = "passed"
            approved_count += 1

        review_notes = f"""
        Similarity score: {max_similarity}
        Quality review:
        {review}
        """.strip()

        save_draft_review(
            draft_id=draft_id,
            book_id=book_id,
            research_run_id=research_run_id,
            task_id=task_id,
            review_type="plagiarism_quality_review",
            review_status=review_status,
            plagiarism_score=max_similarity,
            quality_score=None,
            completeness_score=None,
            review_notes=review_notes,
        )

        update_draft_review(
            draft_id=draft_id,
            draft_status=status,
            review_status=review_status,
            plagiarism_score=max_similarity,
            review_notes=review_notes,
        )

    print("Checker done")
    total_drafts, approved_drafts = get_book_draft_stats(
        book_id,
        research_run_id,
    )
    return {
        "checked_draft_count": checked_count,
        "approved_draft_count": approved_count,
        "revision_draft_count": revision_count,
        "total_draft_count": total_drafts,
        "approved_book_draft_count": approved_drafts,
    }

def get_book_draft_stats(book_id: str, research_run_id: str):
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE draft_status = 'approved'
                        AND review_status = 'passed'
                    ) AS approved
                FROM drafts
                WHERE book_id = %s
                  AND research_run_id = %s
                """,
                (book_id, research_run_id),
            )

            return cur.fetchone()