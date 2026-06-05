from graph import app

result = app.invoke(
    {
        "research_batch_size": 5,
        "completed_research_task_ids": [],
    },
    {
        "recursion_limit": 200
    }
)

print("Done")
print("Completed tasks:", len(result["completed_research_task_ids"]))
print("Draft count:", result.get("draft_count"))