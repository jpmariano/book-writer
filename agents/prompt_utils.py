import re
from typing import Any


def slugify(value: str, max_length: int = 48) -> str:
    """
    Convert a book title into a safe Qdrant collection-name segment.
    """
    value = (value or "untitled_book").lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return (value or "untitled_book")[:max_length].strip("_")


def build_collection_name(book_title: str, book_id: str | None = None) -> str:
    """
    Dynamic collection name based on book title.

    Adding a short book_id suffix prevents collisions when two books have
    the same title.
    """
    title_slug = slugify(book_title)
    suffix = ""

    if book_id:
        suffix = "_" + str(book_id).replace("-", "")[:8]

    return f"book_research_{title_slug}{suffix}"


def format_audience(audience: Any) -> str:
    if isinstance(audience, list):
        return ", ".join(str(item) for item in audience if item)

    return str(audience or "general readers")


def infer_book_kind(book_title: str, book_subject: str | None, genre: str | None) -> str:
    text = f"{book_title} {book_subject or ''} {genre or ''}".lower()

    if any(word in text for word in ["children", "kids", "picture book", "bedtime"]):
        return "children"
    if any(word in text for word in ["programming", "software", "python", "ai", "machine learning", "developer", "computer", "computer science", "ai", "javascript", "engineer", "api", "php", "java"]):
        return "technical"
    if any(word in text for word in ["biology", "physics", "chemistry", "geometry", "math", "science"]):
        return "science"
    if any(word in text for word in ["novel", "fiction", "story", "fantasy", "mystery"]):
        return "fiction"
    if any(word in text for word in ["business", "leadership", "marketing", "finance"]):
        return "business"

    return "general_nonfiction"


def build_research_prompt(
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience: Any,
    topic: str,
) -> str:
    audience_text = format_audience(audience)

    return f"""
You are the Researcher Agent for a book-writing system.

Book title:
{book_title}

Book subject:
{book_subject or "not specified"}

Genre / book type:
{genre or "not specified"}

Target audience:
{audience_text}

Topic to research:
{topic}

Generate 6 useful web search queries for this specific book and audience.

Rules:
- Match the book subject and genre.
- For children's books, prefer age-appropriate educational, story, vocabulary, and visual-reference queries.
- For science and math books, prefer accurate educational sources, definitions, examples, diagrams, and common misconceptions.
- For technical books, prefer documentation, tutorials, design explanations, examples, and implementation details.
- For fiction, prefer setting, background, theme, character, conflict, and worldbuilding research.
- Do not force programming or software terms unless the book is actually technical.

Return only the search queries.
One query per line.
No numbering.
""".strip()


def build_writer_prompt(
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience: Any,
    chapter_title: str,
    topic_title: str,
    research_context: str,
) -> str:
    audience_text = format_audience(audience)
    kind = infer_book_kind(book_title, book_subject, genre)

    technical_context = f"{book_title} {book_subject or ''} {genre or ''} {audience_text}".lower()

    is_code_friendly_book = any(
        word in technical_context
        for word in [
            "computer",
            "computer science",
            "programming",
            "software",
            "developer",
            "engineer",
            "ai",
            "machine learning",
            "data science",
            "python",
            "javascript",
            "api",
            "agent",
        ]
    )

    if is_code_friendly_book:
        code_instruction = """
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
    """.strip()
    else:
        code_instruction = """
    Code sample rules:
    - Only include CODE_SAMPLES if code genuinely helps this subject.
    - For non-programming books, usually return CODE_SAMPLES as [].
    """.strip()

    shared_rules = """
Core rules:
- Write original content based on the research.
- Do not copy source wording.
- Do not closely paraphrase sentence-by-sentence.
- Do not invent facts not supported by the research.
- Match the reading level, tone, and expectations of the target audience.
""".strip()

    if kind == "children":
        specific_rules = """
Children's book rules:
- Use simple, vivid language.
- Keep sentences short and concrete.
- Make the topic feel curious, warm, and easy to imagine.
- Avoid advanced technical explanation unless the audience requires it.
- Use gentle examples, sensory details, and child-friendly comparisons.
- Usually return CODE_SAMPLES as [].
""".strip()
    elif kind == "science":
        specific_rules = """
Science / math book rules:
- Explain the concept clearly and accurately.
- Include definitions, examples, analogies, and common misconceptions.
- Use equations, diagrams, or experiments only when useful.
- Do not include code unless code genuinely helps the topic.
- For geometry or math, make the explanation visual and step-by-step.
""".strip()
    elif kind == "fiction":
        specific_rules = """
Fiction / story rules:
- Write narrative prose, not a textbook explanation.
- Focus on scene, character, conflict, emotion, and sensory detail.
- Keep factual research invisible unless it naturally supports the story.
- Usually return CODE_SAMPLES as [].
""".strip()
    elif kind == "technical":
        specific_rules = """
    Technical book rules:
    - Explain concepts for software engineers and AI engineers.
    - Include implementation details when relevant.
    - Discuss architecture, tradeoffs, workflows, and production considerations.
    - Generate code samples when code helps understanding.
    - Prefer concise, realistic Python examples for AI, backend, APIs, agents, and automation.
    - Do not force code for purely conceptual topics.
    """.strip()
    elif kind == "business":
        specific_rules = """
Business / practical nonfiction rules:
- Be clear, practical, and concrete.
- Use examples, frameworks, decision criteria, and common mistakes.
- Avoid hype and vague motivational language.
- Usually return CODE_SAMPLES as [] unless the topic needs a template or structured example.
""".strip()
    else:
        specific_rules = """
General nonfiction rules:
- Teach the topic clearly.
- Use examples and analogies.
- Avoid unnecessary technical jargon.
- Return CODE_SAMPLES as [] unless code is truly useful.
""".strip()

    return f"""
You are the Writer Agent for a book-making system.

Book title:
{book_title}

Book subject:
{book_subject or "not specified"}

Genre / book type:
{genre or "not specified"}

Target audience:
{audience_text}

Chapter:
{chapter_title}

Topic:
{topic_title}

Research material:
{research_context}

{shared_rules}

{specific_rules}

{code_instruction}

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
""".strip()


def build_style_prompt(
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience: Any,
    chapter_title: str,
    topic_title: str,
    explanations: dict,
) -> str:
    audience_text = format_audience(audience)
    kind = infer_book_kind(book_title, book_subject, genre)

    if kind == "children":
        style_rules = """
Style rules:
- Use warm, simple, age-appropriate language.
- Prefer concrete images over abstract explanation.
- Keep paragraphs short.
- Avoid scary, cynical, or overly adult phrasing.
""".strip()
    elif kind == "fiction":
        style_rules = """
Style rules:
- Make the prose feel like a scene, not an essay.
- Use sensory details and character perspective.
- Avoid explaining what the reader can infer.
""".strip()
    else:
        style_rules = """
Style rules:
- Make the writing clear, natural, and specific.
- Avoid clichés and inflated marketing language.
- Vary sentence length.
- Prefer concrete examples over vague claims.
""".strip()

    return f"""
You are a Senior Editor for this book.

Book title:
{book_title}

Book subject:
{book_subject or "not specified"}

Genre / book type:
{genre or "not specified"}

Target audience:
{audience_text}

Chapter:
{chapter_title}

Topic:
{topic_title}

Current draft:

GENERAL_EXPLANATION:
{explanations["general_explanation"]}

TECHNICAL_EXPLANATION:
{explanations["technical_explanation"]}

{style_rules}

Return exactly this format:

GENERAL_EXPLANATION:
...

TECHNICAL_EXPLANATION:
...
""".strip()


def build_image_prompt(
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience: Any,
    chapter_title: str,
    topic_title: str,
    content_context: str,
) -> str:
    audience_text = format_audience(audience)

    return f"""
You are an instructional design reviewer for a book-making system.

Book title:
{book_title}

Book subject:
{book_subject or "not specified"}

Genre / book type:
{genre or "not specified"}

Target audience:
{audience_text}

Decide whether this topic needs ONE useful image after the written content.

Chapter:
{chapter_title}

Topic:
{topic_title}

Draft content:
{content_context}

Recommend an image only when it would help the reader understand or enjoy the topic.

Examples:
- Children's book: simple illustration, scene, character moment, labeled picture.
- Biology: organism diagram, process diagram, comparison, lifecycle.
- Physics: force diagram, experiment setup, concept diagram.
- Geometry: labeled shape, proof diagram, construction steps.
- Technical book: architecture diagram, flowchart, data flow, sequence diagram.
- Fiction: only if the book format benefits from illustrations.

Return only valid JSON.

If no image is needed:
{{
  "needed": false,
  "reason": "brief reason"
}}

If an image is needed:
{{
  "needed": true,
  "type": "illustration | diagram | flowchart | architecture | sequence | concept_map | timeline | comparison_table | process_diagram | mind_map | uml | erd | network_diagram | venn_diagram | chart | infographic | drawing",
  "title": "short image title",
  "caption": "reader-facing caption",
  "alt_text": "accessible alt text",
  "placement": "after_content",
  "prompt": "detailed prompt for generating or drawing the image",
  "reason": "brief reason"
}}
""".strip()


def build_quality_review_prompt(
    book_title: str,
    book_subject: str | None,
    genre: str | None,
    audience: Any,
    chapter_title: str,
    topic_title: str,
    draft_text: str,
) -> str:
    audience_text = format_audience(audience)

    return f"""
You are a strict quality reviewer for a book-making system.

Book title:
{book_title}

Book subject:
{book_subject or "not specified"}

Genre / book type:
{genre or "not specified"}

Target audience:
{audience_text}

Chapter:
{chapter_title}

Topic:
{topic_title}

Draft:
{draft_text}

Evaluate the draft for:
- completeness for this specific book and audience
- clarity
- originality
- factual accuracy
- age/readinglevel appropriateness
- usefulness or story value, depending on the genre
- whether the style matches the requested book type

Return one of these exact labels first:
APPROVED
NEEDS_REVISION

Then provide short review notes.
""".strip()
