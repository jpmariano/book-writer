from langgraph.graph import StateGraph, START, END

from state.book_state import BookState
from agents.planner import planner
from agents.researcher import researcher
from agents.writer import writer
from agents.plagiarism_checker import plagiarism_checker
from agents.second_writer import second_writer
from agents.asset_generator import asset_generator


def route_after_planner(state: BookState):
    if state.get("has_more_research_tasks"):
        return "researcher"

    return "plagiarism_checker"


def route_after_checker(state: BookState):
    print("route_after_checker revision_draft_count:", state.get("revision_draft_count"))
    print("route_after_checker approved_book_draft_count:", state.get("approved_book_draft_count"))
    print("route_after_checker total_draft_count:", state.get("total_draft_count"))

    if (
        state.get("revision_draft_count", 0) > 0
        and not state.get("stop_revisions", False)
    ):
        return "second_writer"

    total = state.get("total_draft_count", 0)
    approved = state.get("approved_book_draft_count", 0)

    if total > 0 and approved == total:
        return "asset_generator"

    return END


def route_after_second_writer(state: BookState):
    print("route_after_second_writer revised_draft_count:", state.get("revised_draft_count"))
    print("route_after_second_writer stop_revisions:", state.get("stop_revisions"))
    if state.get("revised_draft_count", 0) > 0 and not state.get("stop_revisions", False):
        return "plagiarism_checker"

    return END


graph = StateGraph(BookState)

graph.add_node("planner", planner)
graph.add_node("researcher", researcher)
graph.add_node("writer", writer)
graph.add_node("plagiarism_checker", plagiarism_checker)
graph.add_node("second_writer", second_writer)
graph.add_node("asset_generator", asset_generator)

graph.add_edge(START, "planner")

graph.add_conditional_edges(
    "planner",
    route_after_planner,
    {
        "researcher": "researcher",
        "plagiarism_checker": "plagiarism_checker",
    },
)

graph.add_edge("researcher", "writer")
graph.add_edge("writer", "planner")

graph.add_conditional_edges(
    "plagiarism_checker",
    route_after_checker,
    {
        "second_writer": "second_writer",
        "asset_generator": "asset_generator",
        END: END,
    },
)

graph.add_edge("asset_generator", END)

graph.add_conditional_edges(
    "second_writer",
    route_after_second_writer,
    {
        "plagiarism_checker": "plagiarism_checker",
        END: END,
    },
)

app = graph.compile()
