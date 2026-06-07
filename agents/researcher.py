import uuid
from datetime import datetime, timezone

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_ollama import ChatOllama, OllamaEmbeddings

from agents.websearch import web_search
from state.book_state import BookState
from agents.prompt_utils import build_collection_name, build_research_prompt


POSTGRES_URL = "postgresql://book_writer:book_writer_dev_password@localhost:5432/book_writer"

llm = ChatOllama(
    model="qwen3:8b",
    temperature=0.3,
)

embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)

qdrant = QdrantClient(
    url="http://localhost:6333"
)


def generate_search_queries(
    topic: str,
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience,
) -> list[str]:
    prompt = build_research_prompt(
        book_title=book_title,
        book_subject=book_subject,
        genre=genre,
        audience=audience,
        topic=topic,
    )

    response = llm.invoke(prompt)

    queries = [
        line.strip("-• 1234567890.").strip().strip('"')
        for line in response.content.splitlines()
        if line.strip()
    ]

    return queries[:6]


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def ensure_collection(collection_name: str, vector_size: int):
    existing = [c.name for c in qdrant.get_collections().collections]

    if collection_name not in existing:
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )


def save_source_to_postgres(
    book_id: str,
    research_run_id: str,
    topic: str,
    query: str,
    title: str,
    url: str,
    snippet: str,
    full_text: str,
) -> str:
    source_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_sources (
                    id,
                    book_id,
                    research_run_id,
                    topic,
                    query,
                    source_title,
                    source_url,
                    search_snippet,
                    full_text,
                    content_length,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    source_id,
                    book_id,
                    research_run_id,
                    topic,
                    query,
                    title,
                    url,
                    snippet,
                    full_text,
                    len(full_text),
                    created_at,
                ),
            )

    return source_id


def build_research_documents(
    topic: str,
    book_id: str,
    research_run_id: str,
    collection_name: str,
    search_queries: list[str],
) -> list[dict]:
    documents = []
    seen_urls = set()

    for query in search_queries:
        print(f"Searching: {query}")

        results = web_search(query, max_results=5)

        for result in results:
            title = result.get("title", "")
            url = result.get("href", "")
            snippet = result.get("body", "")

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            # For now, this is still the DDGS snippet.
            # Later, replace this with full page extraction.
            full_text = f"""
Title: {title}
URL: {url}
Search Query: {query}

{snippet}
""".strip()

            source_id = save_source_to_postgres(
                book_id=book_id,
                research_run_id=research_run_id,
                topic=topic,
                query=query,
                title=title,
                url=url,
                snippet=snippet,
                full_text=full_text,
            )

            chunks = chunk_text(full_text)

            for index, chunk in enumerate(chunks):
                documents.append({
                    "text": chunk,
                    "metadata": {
                        "source_id": source_id,
                        "book_id": book_id,
                        "research_run_id": research_run_id,
                        "collection_name": collection_name,
                        "topic": topic,
                        "query": query,
                        "source_title": title,
                        "source_url": url,
                        "chunk_index": index,
                        "chunk_count": len(chunks),
                        "agent": "researcher",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                })

    return documents


def save_documents_to_qdrant(collection_name: str, documents: list[dict]) -> list[str]:
    if not documents:
        return []

    first_vector = embeddings.embed_query(documents[0]["text"])
    ensure_collection(collection_name=collection_name, vector_size=len(first_vector))

    points = []
    stored_ids = []

    for document in documents:
        point_id = str(uuid.uuid4())
        vector = embeddings.embed_query(document["text"])

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "text": document["text"],
                    **document["metadata"],
                },
            )
        )

        stored_ids.append(point_id)

    qdrant.upsert(
        collection_name=collection_name,
        points=points,
    )

    return stored_ids


def researcher(state: BookState):
    print("Researcher started")

    research_batch = state["current_research_batch"]

    book_id = state.get("book_id", str(uuid.uuid4()))
    research_run_id = state.get("research_run_id", str(uuid.uuid4()))

    book_title = state.get("book_title", "Untitled Book")
    book_subject = state.get("book_subject")
    genre = state.get("genre")
    audience = state.get("audience", [])

    collection_name = state.get("vector_collection") or build_collection_name(
        book_title=book_title,
        book_id=book_id,
    )

    all_search_queries = []
    all_documents = []
    completed_task_ids = state.get("completed_research_task_ids", [])

    for task in research_batch:
        topic = task["topic_title"]

        print(f"Researching topic: {topic}")

        search_queries = generate_search_queries(
            topic=topic,
            book_title=book_title,
            book_subject=book_subject,
            genre=genre,
            audience=audience,
        )
        all_search_queries.extend(search_queries)

        documents = build_research_documents(
            topic=topic,
            book_id=book_id,
            research_run_id=research_run_id,
            collection_name=collection_name,
            search_queries=search_queries,
        )

        all_documents.extend(documents)

    print("Saving research chunks to Qdrant...")
    stored_ids = save_documents_to_qdrant(collection_name, all_documents)

    print("Researcher done")

    return {
        "book_id": book_id,
        "research_run_id": research_run_id,
        "vector_collection": collection_name,
        "search_queries": all_search_queries,
        "research_chunk_ids": stored_ids,
        "research_item_count": len(all_documents)
    }