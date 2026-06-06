import uuid
from datetime import datetime, timezone

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from langchain_ollama import ChatOllama, OllamaEmbeddings

from state.book_state import BookState


COLLECTION_NAME = "book_research"
POSTGRES_URL = "postgresql://book_writer:book_writer_dev_password@localhost:5432/book_writer"

llm = ChatOllama(model="qwen3:8b", temperature=0.6)
embeddings = OllamaEmbeddings(model="nomic-embed-text")
qdrant = QdrantClient(url="http://localhost:6333")


def retrieve_research_chunks(
    query: str,
    book_id: str,
    research_run_id: str,
    limit: int = 10,
) -> list[dict]:
    query_vector = embeddings.embed_query(query)

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
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


def write_explanations(topic_title: str, chapter_title: str, chunks: list[dict]) -> dict:
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

    prompt = f"""
You are the Writer Agent for a technical book.

Chapter:
{chapter_title}

Topic:
{topic_title}

Research material:
{research_context}

Write original content based on the research.

Rules:
- Do not copy source wording.
- Do not closely paraphrase sentence-by-sentence.
- Explain the ideas in your own structure.
- Use clear examples.
- Make it useful for software engineers and AI engineers.
- Do not invent facts not supported by the research.

Return exactly this format:

GENERAL_EXPLANATION:
Write a clear beginner-friendly explanation.

TECHNICAL_EXPLANATION:
Write a deeper technical explanation for engineers.
"""

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
        "general_explanation": general,
        "technical_explanation": technical,
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
                    used_source_ids,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            limit=10,
        )

        explanations = write_explanations(
            topic_title=topic_title,
            chapter_title=chapter_title,
            chunks=chunks,
        )

        used_source_ids = list({
            chunk["source_id"]
            for chunk in chunks
            if chunk.get("source_id")
        })

        draft_id = save_draft_to_postgres(
            book_id=book_id,
            research_run_id=research_run_id,
            task_id=task_id,
            chapter_title=chapter_title,
            topic_title=topic_title,
            general_explanation=explanations["general_explanation"],
            technical_explanation=explanations["technical_explanation"],
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