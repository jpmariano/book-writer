from typing import TypedDict, List, Dict, Any


class BookState(TypedDict, total=False):
    topic: str
    search_queries: List[str]
    research_results: List[Dict[str, Any]]
    research_notes: str