from langchain_ollama import ChatOllama
from agents.websearch import web_search
from state.book_state import BookState
from prompts.book_outline_prompt import book_outline_prompt

llm = ChatOllama(
    model="qwen3:8b",
    temperature=0.3,
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


def summarize_research(topic: str, results: list[dict]) -> str:
    formatted_results = ""

    for item in results:
        formatted_results += f"""
Title: {item.get("title")}
URL: {item.get("href")}
Snippet: {item.get("body")}
"""

    prompt = f"""
You are a research assistant helping write a book.

Book topic:
{topic}

Search results:
{formatted_results}

Create useful research notes for a writer.

Include:
- key ideas
- important facts
- examples
- trends
- possible chapter angles
- useful sources

Keep it organized and practical.
"""

    response = llm.invoke(prompt)
    return response.content


def researcher(state):
    print("Researcher started")
    print(state)
    topic = state["topic"]

    print("Generating queries...")
    search_queries = generate_search_queries(topic)

    print(search_queries)

    all_results = []

    for query in search_queries:
        print(f"Searching: {query}")

        results = web_search(query)

        all_results.extend(results)

    print("Summarizing...")

    research_notes = summarize_research(
        topic,
        all_results
    )

    print("Done")

    return {
        "search_queries": search_queries,
        "research_results": all_results,
        "research_notes": research_notes,
    }