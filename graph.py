from langgraph.graph import StateGraph, START, END

from state.book_state import BookState
from agents.researcher import researcher
from agents.writer import writer
from agents.plagiarism_checker import plagiarism_checker

graph = StateGraph(BookState)

graph.add_node("researcher", researcher)
#graph.add_node("writer", writer)
#graph.add_node("checker", plagiarism_checker)

graph.add_edge(START, "researcher")
graph.add_edge("researcher", END)
#graph.add_edge("researcher", "writer")
#graph.add_edge("writer", "checker")
#graph.add_edge("checker", END)

app = graph.compile()