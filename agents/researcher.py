# agents/researcher.py
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def researcher(state):
    # Step 1: Search for articles related to "building agentic applications"
    search_query = "building agentic applications"
    search_results = web_search(search_query)

    # Step 2: Get the save directory from .env
    save_dir = os.getenv("ARTICLE_SAVE_DIR", "articles")  # Default to 'articles' if not set

    # Step 3: Create the directory if it doesn't exist
    os.makedirs(save_dir, exist_ok=True)

    # Step 4: Save each article to a file
    saved_articles = []
    for i, result in enumerate(search_results, start=1):
        file_name = f"{save_dir}/article_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(file_name, "w") as f:
            f.write(result)
        saved_articles.append(file_name)

    # Step 5: Return the research notes with the saved article paths
    return {
        "research_notes": f"Found {len(search_results)} articles. Saved to: {', '.join(saved_articles)}"
    }