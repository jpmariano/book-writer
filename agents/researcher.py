import uuid
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from langchain_ollama import ChatOllama, OllamaEmbeddings

from agents.websearch import web_search
from state.book_state import BookState


COLLECTION_NAME = "book_research"

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


def generate_search_queries(topic: str) -> list[str]:
    prompt = f"""
You are the researcher agent for a book-writing system.

Book topic:
{topic}

Generate 6 useful web search queries for researching this book.

Return only the search queries.
One query per line.
No numbering.
"""

    response = llm.invoke(prompt)

    queries = [
        line.strip("-• 1234567890.").strip()
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


def ensure_collection(vector_size: int):
    existing = [c.name for c in qdrant.get_collections().collections]

    if COLLECTION_NAME not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )


def build_research_documents(
    topic: str,
    book_id: str,
    research_run_id: str,
    search_queries: list[str],
) -> list[dict]:
    documents = []

    for query in search_queries:
        print(f"Searching: {query}")

        results = web_search(query, max_results=5)

        for result in results:
            title = result.get("title", "")
            url = result.get("href", "")
            snippet = result.get("body", "")

            text = f"""
Title: {title}
URL: {url}
Search Query: {query}

{snippet}
""".strip()

            chunks = chunk_text(text)

            for index, chunk in enumerate(chunks):
                documents.append({
                    "text": chunk,
                    "metadata": {
                        "book_id": book_id,
                        "research_run_id": research_run_id,
                        "topic": topic,
                        "query": query,
                        "source_title": title,
                        "source_url": url,
                        "chunk_index": index,
                        "agent": "researcher",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                })

    return documents


def save_documents_to_qdrant(documents: list[dict]) -> list[str]:
    if not documents:
        return []

    first_vector = embeddings.embed_query(documents[0]["text"])
    ensure_collection(vector_size=len(first_vector))

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
        collection_name=COLLECTION_NAME,
        points=points,
    )

    return stored_ids


def researcher(state: BookState):
    print("Researcher started")

    topic = state["topic"]

    book_id = state.get("book_id", str(uuid.uuid4()))
    research_run_id = state.get("research_run_id", str(uuid.uuid4()))

    print("Generating search queries...")
    search_queries = generate_search_queries(topic)

    print("Building research documents...")
    documents = build_research_documents(
        topic=topic,
        book_id=book_id,
        research_run_id=research_run_id,
        search_queries=search_queries,
    )

    print("Saving research chunks to Qdrant...")
    stored_ids = save_documents_to_qdrant(documents)

    print("Researcher done")

    return {
        "book_id": book_id,
        "research_run_id": research_run_id,
        "vector_collection": COLLECTION_NAME,
        "search_queries": search_queries,
        "research_chunk_ids": stored_ids,
        "research_item_count": len(documents),
    }