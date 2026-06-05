from langgraph.graph import StateGraph, START, END

from state.book_state import BookState
from agents.planner import planner
from agents.researcher import researcher


graph = StateGraph(BookState)

graph.add_node("planner", planner)
graph.add_node("researcher", researcher)

graph.add_edge(START, "planner")
graph.add_edge("planner", "researcher")
graph.add_edge("researcher", END)

app = graph.compile()