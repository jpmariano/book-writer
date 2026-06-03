# state/book_state.py
from typing import TypedDict

class BookState(TypedDict):
    current_chapter: int
    total_chapters: int
    progress: float
    notes: str
