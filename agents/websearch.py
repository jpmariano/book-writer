

from ddgs import DDGS


def web_search(query: str, max_results: int = 10):
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))