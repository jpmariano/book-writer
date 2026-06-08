from typing import TypedDict, List, Dict, Any


class BookState(TypedDict, total=False):
    book_id: str
    research_run_id: str
    vector_collection: str

    book_title: str
    audience: List[str]
    book_subject: str
    genre: str
    tone: str
    reading_level: str

    all_research_tasks: List[Dict[str, Any]]
    current_research_batch: List[Dict[str, Any]]
    completed_research_task_ids: List[str]
    has_more_research_tasks: bool
    research_batch_size: int

    search_queries: List[str]
    research_chunk_ids: List[str]
    research_item_count: int

    draft_ids: List[str]
    draft_count: int

    checked_draft_count: int
    approved_draft_count: int
    revision_draft_count: int

    revised_draft_count: int
    stop_revisions: bool
    revision_round: int
    max_revision_rounds: int

    total_draft_count: int
    approved_book_draft_count: int

