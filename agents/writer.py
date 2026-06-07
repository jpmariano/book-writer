import uuid
from datetime import datetime, timezone

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from langchain_ollama import ChatOllama, OllamaEmbeddings
from psycopg.types.json import Jsonb
from state.book_state import BookState
import json
import re

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

CODE SAMPLE GENERATION:
Determine whether the topic would benefit from code examples.

Generate code examples when:
- Explaining APIs
- Frameworks
- Libraries
- Algorithms
- Design patterns
- Configuration
- Infrastructure
- AI/ML workflows
- Database operations
- Debugging techniques

Do NOT generate code when:
- The topic is purely conceptual
- The topic is historical
- The topic is organizational or management focused

Requirements:
- Examples must be realistic and runnable.
- Use the most appropriate language.
- Prefer Python for AI and backend topics.
- Prefer JavaScript/TypeScript for frontend topics.
- Keep examples concise.
- Include brief comments where useful.  

Return exactly this format:

GENERAL_EXPLANATION:
Write a clear beginner-friendly explanation.

TECHNICAL_EXPLANATION:
Write a deeper technical explanation for engineers.

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

def style_revision(topic_title: str, chapter_title: str, explanations: dict) -> dict:
    prompt = f"""
Role: You are a Senior Editor and Human Copywriter. 
Your objective is to rewrite AI-generated text to make it sound authentic, engaging, and written by a real human being. 
Your goal is to make the writing clearer, more natural, more specific, and more useful to readers.

Chapter:
{chapter_title}

Topic:
{topic_title}

Current draft:

GENERAL_EXPLANATION:
{explanations["general_explanation"]}

TECHNICAL_EXPLANATION:
{explanations["technical_explanation"]}


STYLE GUIDELINES:
- **NO PATHOS:** Avoid grandiose words (e.g., "paramount," "unparalleled," "groundbreaking"). Keep it grounded.
- **NO CLICHÉS:** Strictly forbid these phrases: "unlock potential," "next level," "game-changer," "seamless," "fast-paced world," "delve," "landscape," "testament to," "leverage."
- **VARY RHYTHM:** Use "burstiness." Mix very short sentences with longer, complex ones. Avoid monotone structure.
- **BE SUBJECTIVE:** Use "I," "We," "In my experience." Avoid passive voice.
- **NO TAUTOLOGY:** Do not repeat the same nouns or verbs in adjacent sentences.

FEW-SHOT EXAMPLES (Learn from this): 
❌ **AI Style:** "In today's digital landscape, it is paramount to leverage innovative solutions to unlock your potential."
✅ **Human Style:** "Look, the digital world moves fast. If you want to grow, you need tools that actually work, not just buzzwords."

❌ **AI Style:** "This comprehensive guide delves into the key aspects of optimization."
✅ **Human Style:** "In this guide, we'll break down exactly how to optimize your workflow without the fluff.

WORKFLOW: Silently analyze, plan, rewrite, and review. Do not show your analysis or plan. Only return the final rewritten content.

Return exactly this format:

Chapter:
{chapter_title}

Topic:
{topic_title}

GENERAL_EXPLANATION:
...

TECHNICAL_EXPLANATION:
...
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


def decide_image_need(topic_title: str, chapter_title: str, explanations: dict) -> dict | None:
    """
    Decide whether this draft needs one explanatory image.

    Returns a JSON-serializable image spec when an image would help.
    Returns None when text/code is enough.
    """
    content_context = build_image_context(explanations)

    prompt = f"""
You are an instructional design reviewer for a technical book.

Decide whether this topic needs ONE explanatory image after the written content.

Chapter:
{chapter_title}

Topic:
{topic_title}

Draft content:
{content_context}

Only recommend an image when the concept is hard to grasp from text alone.

Recommend an image for:
- Complex architecture
- Multi-step workflows
- Data flow
- System interactions
- Abstract AI/ML concepts
- Algorithms that are easier to understand visually
- Comparisons with multiple moving parts
- Concepts where a reader benefits from seeing relationships

Do NOT recommend an image for:
- Simple definitions
- Mostly historical/background topics
- Topics already made clear by code samples
- Short practical tips
- Content that would only produce a decorative stock image

Return only valid JSON.

If no image is needed:
{{
  "needed": false,
  "reason": "brief reason"
}}

If an image is needed:
{{
  "needed": true,
  "type": "diagram | flowchart | architecture | sequence | concept_map",
  "title": "short image title",
  "caption": "reader-facing caption",
  "alt_text": "accessible alt text",
  "placement": "after_content",
  "prompt": "detailed prompt for generating or drawing the image",
  "reason": "brief reason"
}}
"""

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

        raw_explanations = write_explanations(
            topic_title=topic_title,
            chapter_title=chapter_title,
            chunks=chunks,
        )

        explanations = style_revision(
            topic_title=topic_title,
            chapter_title=chapter_title,
            explanations=raw_explanations,
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


