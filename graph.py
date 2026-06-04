from langgraph.graph import StateGraph, START, END

from state.book_state import BookState
from agents.researcher import researcher


graph = StateGraph(BookState)

graph.add_node("researcher", researcher)

graph.add_edge(START, "researcher")
graph.add_edge("researcher", END)

app = graph.compile()