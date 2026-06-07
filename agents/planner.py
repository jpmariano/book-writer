import uuid
from pathlib import Path
from typing import Any

import yaml


from state.book_state import BookState


BOOK_GUIDE_PATH = Path("guide/book.yml")
DEFAULT_BATCH_SIZE = 5


def load_book_guide(path: Path = BOOK_GUIDE_PATH) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def flatten_book_topics(book_guide: dict[str, Any]) -> list[dict[str, Any]]:
    book = book_guide["book"]

    book_title = book.get("book_title") or book.get("title")
    if not book_title:
        raise ValueError("book.yml must contain book.book_title or book.title")
    audience = book.get("audience", [])

    tasks = []
    topic_counter = 0

    for part_index, part in enumerate(book.get("parts", []), start=1):
        part_title = part["part"]

        for chapter_index, chapter in enumerate(part.get("chapters", []), start=1):
            chapter_title = chapter["chapter"]

            for topic_index, topic_title in enumerate(chapter.get("topics", []), start=1):
                topic_counter += 1

                tasks.append({
                    "task_id": make_task_id(part_index, chapter_index, topic_index),
                    "book_title": book_title,
                    "audience": audience,
                    "part_index": part_index,
                    "part_title": part_title,
                    "chapter_index": chapter_index,
                    "chapter_title": chapter_title,
                    "topic_index": topic_index,
                    "topic_title": topic_title,
                    "global_topic_index": topic_counter,
                    "status": "pending",
                })

    return tasks


def get_next_batch(
    tasks: list[dict[str, Any]],
    completed_task_ids: list[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[dict[str, Any]]:
    completed = set(completed_task_ids)

    pending_tasks = [
        task for task in tasks
        if task["task_id"] not in completed
    ]

    return pending_tasks[:batch_size]


def planner(state: BookState):
    print("Planner started")

    book_guide = load_book_guide()
    all_research_tasks = flatten_book_topics(book_guide)

    completed_task_ids = state.get("completed_research_task_ids", [])

    research_batch = get_next_batch(
        tasks=all_research_tasks,
        completed_task_ids=completed_task_ids,
        batch_size=state.get("research_batch_size", DEFAULT_BATCH_SIZE),
    )

    print(f"Total research tasks: {len(all_research_tasks)}")
    print(f"Next batch size: {len(research_batch)}")

    return {
        "book_title": book_guide["book"].get("book_title") or book_guide["book"].get("title"),
        "audience": book_guide["book"].get("audience", []),
        "all_research_tasks": all_research_tasks,
        "current_research_batch": research_batch,
        "has_more_research_tasks": len(research_batch) > 0,
    }

def make_task_id(part_index, chapter_index, topic_index):
    return f"part-{part_index}-chapter-{chapter_index}-topic-{topic_index}"