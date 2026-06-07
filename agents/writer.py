import uuid
from datetime import datetime, timezone

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from langchain_ollama import ChatOllama, OllamaEmbeddings
from psycopg.types.json import Jsonb
from state.book_state import BookState
from agents.prompt_utils import build_collection_name, build_writer_prompt, build_style_prompt, build_image_prompt
import json
import re

POSTGRES_URL = "postgresql://book_writer:book_writer_dev_password@localhost:5432/book_writer"

llm = ChatOllama(model="qwen3:8b", temperature=0.6)
embeddings = OllamaEmbeddings(model="nomic-embed-text")
qdrant = QdrantClient(url="http://localhost:6333")


def retrieve_research_chunks(
    query: str,
    book_id: str,
    research_run_id: str,
    collection_name: str,
    limit: int = 10,
) -> list[dict]:
    query_vector = embeddings.embed_query(query)

    results = qdrant.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="book_id",
                    match=MatchValue(value=book_id),
                ),
                FieldCondition(
                    key="research_run_id",
                    match=MatchValue(value=research_run_id),
                ),
            ]
        ),
        limit=limit,
        with_payload=True,
    )

    chunks = []

    for point in results.points:
        chunks.append({
            "score": point.score,
            "text": point.payload.get("text", ""),
            "source_id": point.payload.get("source_id"),
            "source_title": point.payload.get("source_title"),
            "source_url": point.payload.get("source_url"),
        })

    return chunks


def write_explanations(
    topic_title: str,
    chapter_title: str,
    chunks: list[dict],
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience,
) -> dict:
    research_context = ""

    for index, chunk in enumerate(chunks, start=1):
        research_context += f"""
SOURCE {index}
Source ID: {chunk["source_id"]}
Title: {chunk["source_title"]}
URL: {chunk["source_url"]}

Research:
{chunk["text"]}
"""

    prompt = build_writer_prompt(
        book_title=book_title,
        book_subject=book_subject,
        genre=genre,
        audience=audience,
        chapter_title=chapter_title,
        topic_title=topic_title,
        research_context=research_context,
    )

    response = llm.invoke(prompt)
    content = response.content

    code_samples = extract_code_samples(content)

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

def style_revision(
    topic_title: str,
    chapter_title: str,
    explanations: dict,
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience,
) -> dict:
    prompt = build_style_prompt(
        book_title=book_title,
        book_subject=book_subject,
        genre=genre,
        audience=audience,
        chapter_title=chapter_title,
        topic_title=topic_title,
        explanations=explanations,
    )

    response = llm.invoke(prompt)
    content = response.content

    general = ""
    technical = ""

    if "TECHNICAL_EXPLANATION:" in content:
        before, technical = content.split("TECHNICAL_EXPLANATION:", 1)
        general = before.replace("GENERAL_EXPLANATION:", "").strip()
        technical = technical.strip()
    else:
        general = content.strip()

    return {
        "chapter": chapter_title,
        "topic": topic_title,
        "general_explanation": general,
        "technical_explanation": technical,
        "code_samples": explanations.get("code_samples", []),
    }

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


def build_image_context(explanations: dict) -> str:
    return f"""
GENERAL_EXPLANATION:
{explanations.get("general_explanation", "")}

TECHNICAL_EXPLANATION:
{explanations.get("technical_explanation", "")}

CODE_SAMPLES:
{json.dumps(explanations.get("code_samples", []), ensure_ascii=False)}
""".strip()


def decide_image_need(
    topic_title: str,
    chapter_title: str,
    explanations: dict,
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience,
) -> dict | None:
    """
    Decide whether this draft needs one explanatory image.

    Returns a JSON-serializable image spec when an image would help.
    Returns None when text/code is enough.
    """
    content_context = build_image_context(explanations)

    prompt = build_image_prompt(
        book_title=book_title,
        book_subject=book_subject,
        genre=genre,
        audience=audience,
        chapter_title=chapter_title,
        topic_title=topic_title,
        content_context=content_context,
    )

    response = llm.invoke(prompt)
    raw = response.content.strip()

    try:
        decision = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            decision = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not decision.get("needed"):
        return None

    return {
        "type": decision.get("type", "diagram"),
        "title": decision.get("title", f"{topic_title} diagram"),
        "caption": decision.get("caption", ""),
        "alt_text": decision.get("alt_text", ""),
        "placement": decision.get("placement", "after_content"),
        "prompt": decision.get("prompt", ""),
        "reason": decision.get("reason", ""),
    }

def save_draft_to_postgres(
    book_id: str,
    research_run_id: str,
    task_id: str,
    chapter_title: str,
    topic_title: str,
    general_explanation: str,
    technical_explanation: str,
    used_source_ids: list[str],
    code_samples: list[dict],
    image: dict | None = None,
) -> str:
    draft_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO drafts (
                    id,
                    book_id,
                    research_run_id,
                    task_id,
                    chapter_title,
                    topic_title,
                    general_explanation,
                    technical_explanation,
                    code_samples,
                    image,
                    used_source_ids,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    draft_id,
                    book_id,
                    research_run_id,
                    task_id,
                    chapter_title,
                    topic_title,
                    general_explanation,
                    technical_explanation,
                    Jsonb(code_samples),
                    Jsonb(image) if image is not None else None,
                    used_source_ids,
                    created_at,
                ),
            )

    return draft_id


def writer(state: BookState):
    print("Writer started")
    completed_task_ids = state.get("completed_research_task_ids", []).copy()
    book_id = state["book_id"]
    research_run_id = state["research_run_id"]
    research_batch = state["current_research_batch"]

    book_title = state.get("book_title", "Untitled Book")
    book_subject = state.get("book_subject")
    genre = state.get("genre")
    audience = state.get("audience", [])

    collection_name = state.get("vector_collection") or build_collection_name(
        book_title=book_title,
        book_id=book_id,
    )

    draft_ids = []

    for task in research_batch:
        topic_title = task["topic_title"]
        chapter_title = task["chapter_title"]
        task_id = task["task_id"]

        print(f"Writing topic: {topic_title}")

        query = f"{chapter_title}: {topic_title}"

        chunks = retrieve_research_chunks(
            query=query,
            book_id=book_id,
            research_run_id=research_run_id,
            collection_name=collection_name,
            limit=10,
        )

        raw_explanations = write_explanations(
            topic_title=topic_title,
            chapter_title=chapter_title,
            chunks=chunks,
            book_title=book_title,
            book_subject=book_subject,
            genre=genre,
            audience=audience,
        )

        explanations = style_revision(
            topic_title=topic_title,
            chapter_title=chapter_title,
            explanations=raw_explanations,
            book_title=book_title,
            book_subject=book_subject,
            genre=genre,
            audience=audience,
        )

        used_source_ids = list({
            chunk["source_id"]
            for chunk in chunks
            if chunk.get("source_id")
        })

        image = decide_image_need(
            topic_title=topic_title,
            chapter_title=chapter_title,
            explanations=explanations,
            book_title=book_title,
            book_subject=book_subject,
            genre=genre,
            audience=audience,
        )

        draft_id = save_draft_to_postgres(
            book_id=book_id,
            research_run_id=research_run_id,
            task_id=task_id,
            chapter_title=chapter_title,
            topic_title=topic_title,
            general_explanation=explanations["general_explanation"],
            technical_explanation=explanations["technical_explanation"],
            code_samples=explanations.get("code_samples", []),
            image=image,
            used_source_ids=used_source_ids,
        )

        draft_ids.append(draft_id)
        completed_task_ids.append(task_id)

    print("Writer done")
    
    return {
        "draft_ids": draft_ids,
        "draft_count": len(draft_ids),
        "completed_research_task_ids": completed_task_ids,
    }


