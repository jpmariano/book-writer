# Check Qdrant is running
```bash
curl http://localhost:6333
```

# List collections
```bash
curl http://localhost:6333/collections
```
# Get collection info
```bash
curl http://localhost:6333/collections/book_research
```

# To delete a collection in Qdrant
```bash
curl -X DELETE http://localhost:6333/collections/book_research
```

# Scroll records from your collection
```bash
curl -X POST http://localhost:6333/collections/book_research/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 5,
    "with_payload": true,
    "with_vector": false
  }'

  curl -X POST http://localhost:6333/collections/book_research/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "with_payload": true,
    "with_vector": false
  }'
```
# book_id
```bash
curl -X POST http://localhost:6333/collections/book_research/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [
        {
          "key": "book_id",
          "match": {
            "value": "98a6ae1a-1838-4759-8ec7-491e03a9d7a9"
          }
        }
      ]
    },
    "limit": 5,
    "with_payload": true,
    "with_vector": false
  }'
```
# Filter by book_id and research_run_id
```bash
curl -X POST http://localhost:6333/collections/book_research/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [
        {
          "key": "book_id",
          "match": {
            "value": "3dce69c8-9808-4706-90b5-f1bb854f35b4"
          }
        },
        {
          "key": "research_run_id",
          "match": {
            "value": "d1d75dd2-8324-4bd0-a91c-29d4f3660022"
          }
        }
      ]
    },
    "limit": 10,
    "with_payload": true,
    "with_vector": false
  }'

  curl -X POST http://localhost:6333/collections/book_research/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [
            { "has_id": ["02f970f0-2172-4265-958f-381ca6277a22"] }
        ]
    },
    "with_payload": true,
    "with_vector": false
  }'

  curl -X POST http://localhost:6333/collections/book_research/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "with_payload": false,
    "with_vector": false
  }'

  curl -X POST http://localhost:6333/collections/book_research/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [
        {
          "key": "source_url",
          "match": {
            "value": "https://arxiv.org/html/2601.03624v1"
          }
        }
      ]
    },
    "limit": 200,
    "with_payload": true,
    "with_vector": false
  }'

  curl -X POST http://localhost:6333/collections/book_research/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [
        {
          "key": "book_id",
          "match": {
            "value": "ffbdabf5-21cb-4979-807d-44481c28da97"
          }
        },
        {
          "key": "source_url",
          "match": {
            "value": "https://arxiv.org/html/2601.03624v1"
          }
        }
      ]
    },
    "limit": 200,
    "with_payload": true,
    "with_vector": false
  }'

  ddgs extract -u www.example.com -f text_plain

 

```
# Starting Docker Compose
```bash
docker compose up -d
```
# Stopping Docker Compose
```bash
docker compose down
```

# Delete data too
```bash
docker compose down -v
```

# Find the actual location of volume
```bash
docker volume ls
```
## Output Volume
```bash
DRIVER    VOLUME NAME
local     book-writer_qdrant_storage
```

### Instpect Volume
```bash
docker volume inspect book-writer_qdrant_storage
```

# Check Qdrant is running
```bash
```
# Check Qdrant is running
```bash
```
# Check Qdrant is running
```bash
```
# Check Qdrant is running
```bash
```
# Check Qdrant is running
```bash
```
# Check Qdrant is running
```bash
```
# Check Qdrant is running
```bash
```
# Check Qdrant is running
```bash
```
# Check Qdrant is running
```bash
```

My researcher agent can now save to the quadrant database. Now help me write my writer.py. The writer.py should get all the latest 6 research content from quadrant. And write contents base on the researched items. 