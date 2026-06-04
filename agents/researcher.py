
from agents.websearch import web_search
from state.book_state import BookState

def researcher(state: BookState):
    topic = state["topic"]

    results = web_search(topic)

    notes = []
    for item in results:
        notes.append(
            f"Title: {item.get('title')}\n"
            f"URL: {item.get('href')}\n"
            f"Summary: {item.get('body')}"
        )

    return {
        "research_results": results,
        "research_notes": "\n\n".join(notes),
    }