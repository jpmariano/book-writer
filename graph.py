from langgraph.graph import StateGraph, START, END

from state.book_state import BookState
from agents.planner import planner
from agents.researcher import researcher
from agents.writer import writer


def route_after_planner(state: BookState):
    if state.get("has_more_research_tasks"):
        return "researcher"

    return END


graph = StateGraph(BookState)

graph.add_node("planner", planner)
graph.add_node("researcher", researcher)
graph.add_node("writer", writer)

graph.add_edge(START, "planner")

graph.add_conditional_edges(
    "planner",
    route_after_planner,
    {
        "researcher": "researcher",
        END: END,
    },
)

graph.add_edge("researcher", "writer")
graph.add_edge("writer", "planner")

app = graph.compile()