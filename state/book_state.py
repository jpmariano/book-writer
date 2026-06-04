from typing import TypedDict, List


class BookState(TypedDict, total=False):
    topic: str
    book_id: str
    research_run_id: str
    vector_collection: str
    search_queries: List[str]
    research_chunk_ids: List[str]
    research_item_count: int