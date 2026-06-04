from dotenv import load_dotenv
from graph import app

load_dotenv()

result = app.invoke({
    "topic": "Building Modern Agentic Applications"
})

print("\nSEARCH QUERIES:")
for query in result["search_queries"]:
    print("-", query)

print("\nRESEARCH NOTES:")
print(result)