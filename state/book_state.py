from typing import TypedDict, List, Dict, Any


class BookState(TypedDict, total=False):
    topic: str
    book_id: str
    research_run_id: str
    vector_collection: str
    book_title: str
    audience: List[str]
    all_research_tasks: List[Dict[str, Any]]
    current_research_batch: List[Dict[str, Any]]
    completed_research_task_ids: List[str]
    research_batch_size: int
    search_queries: List[str]
    research_chunk_ids: List[str]
    research_item_count: int