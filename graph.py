from langgraph.graph import StateGraph, START, END

from state.book_state import BookState
from agents.planner import planner
from agents.researcher import researcher
from agents.writer import writer
from agents.plagiarism_checker import plagiarism_checker


def route_after_planner(state: BookState):
    if state.get("has_more_research_tasks"):
        return "researcher"

    return "plagiarism_checker"


graph = StateGraph(BookState)

graph.add_node("planner", planner)
graph.add_node("researcher", researcher)
graph.add_node("writer", writer)
graph.add_node("plagiarism_checker", plagiarism_checker)

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
graph.add_edge("plagiarism_checker", END)

app = graph.compile()