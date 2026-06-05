from graph import app

result = app.invoke({
    "research_batch_size": 5,
    "completed_research_task_ids": [],
})

print("\nBOOK:")
print(result["book_title"])

print("\nCURRENT RESEARCH BATCH:")
for task in result["current_research_batch"]:
    print("-", task["chapter_title"], "→", task["topic_title"])