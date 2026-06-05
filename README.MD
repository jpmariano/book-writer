pip install pipreqs
pipreqs .  

export OLLAMA_MAX_LOADED_MODELS=3
export OLLAMA_NUM_PARALLEL=2
ollama serve

ollama pull llama3
ollama pull mistral
ollama pull phi3


Method A: Using Independent TerminalsOpen three separate terminal windows. Run one unique command in each window:Terminal 1: ollama run llama3Terminal 2: ollama run mistralTerminal 3: ollama run phi3

# Request to Model 1
curl http://localhost:11434/api/generate -d '{"model": "llama3", "prompt": "Why is the sky blue?"}'

# Request to Model 2
curl http://localhost:11434/api/generate -d '{"model": "mistral", "prompt": "Write a poem about rain."}'


docker run -p 6333:6333 -p 6334:6334 --name book-writer qdrant/qdrant

docker run --name <nameyourcontainer> <reponame>:<tag>
pip install qdrant-client langchain-ollama
ollama pull nomic-embed-text

pip install "psycopg[binary]"
```sql
CREATE TABLE IF NOT EXISTS research_sources (
    id UUID PRIMARY KEY,
    book_id UUID NOT NULL,
    research_run_id UUID NOT NULL,
    topic TEXT NOT NULL,
    query TEXT NOT NULL,
    source_title TEXT,
    source_url TEXT,
    search_snippet TEXT,
    full_text TEXT,
    content_length INTEGER,
    created_at TIMESTAMPTZ NOT NULL,
    task_id TEXT,
    book_title Text, 
    audience TEXT[],
    part_title TEXT,
    chapter_title TEXT,
    topic_title TEXT,
    task_metadata JSONB,
    global_topic_index INTEGER
);
```
```bash
\dt #Lists all tables in the current (public) schema.
\dt #Lists all tables across all schemas, including system tables.
\dt+ #Lists tables with extra details like size and descriptions.
\d #Lists all tables, views, and sequences combined.
\d #table_name – Inspects columns and data types for a specific
DROP TABLE research_sources;
TRUNCATE TABLE research_sources;
curl -X DELETE http://localhost:6333/collections/book_research
```
You can run it with:
```bash
docker exec -it book-writer-postgres psql -U book_writer -d book_writer

\dt
\d research_sources
SELECT COUNT(*) FROM research_sources;
SELECT
    id,
    source_title,
    source_url,
    full_text
FROM research_sources
LIMIT 5;

SELECT COUNT(*) FROM research_sources;
SELECT
    id,
    full_text
FROM research_sources
LIMIT 1;

TRUNCATE TABLE research_sources;

\q

pip install pyyaml
```