from graph import app

result = app.invoke({
    "topic": "Building Modern Agentic Applications"
})

print(result["research_notes"])