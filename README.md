# HF-Space Microservice

A standalone microservice providing PDF text extraction via PyMuPDF (AGPL-3.0) and an RQ worker for asynchronous processing.  
This service is designed to live in its own container/repository so that your main `extralit/extralit-server` codebase can remain under Apache-2.0, avoiding direct linkage to AGPL-licensed code.

## Features

- FastAPI HTTP endpoint (`POST /extract`) to upload a PDF and receive extracted plain text.
- RQ worker listening on the `pymupdf` Redis queue for background extraction jobs.
- Bundled Elasticsearch (8.x) and Redis servers for local development and easy deployment.
- Honcho/Procfile to orchestrate web server + worker in a single container.
- All AGPL-licensed logic (PyMuPDF) is fully isolated here.

## Requirements

- Docker & Docker Buildx (for multi-arch builds)
- Redis server (if running outside Docker)
- Elasticsearch 8.x (if running outside Docker)
- Python 3.11+

## Repository Layout

```
hf-space/
├─ app.py                  # FastAPI service for PDF extraction
├─ worker.py               # RQ worker entrypoint (queue: pymupdf)
├─ requirements.txt        # Python dependencies
├─ Dockerfile              # Builds container with FastAPI, worker, Redis & ES
├─ Procfile                # Defines `web` and `worker` processes for Honcho
├─ scripts/
│   └─ start.sh            # Honcho startup wrapper
└─ config/
    └─ elasticsearch.yml   # Elasticsearch configuration
```

## Installation & Local Development

1. Clone the repo:
   ```bash
   git clone <your-url>/hf-space.git
   cd hf-space
   ```
2. Create a Python virtualenv and install dependencies:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Start Redis and Elasticsearch (e.g. via Docker Compose or local binaries):
   ```bash
   docker run -d --name redis -p 6379:6379 redis:7
   docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" elasticsearch:8.17.0
   ```
4. Launch the API and worker (in separate terminals):
   ```bash
   # Terminal 1 — API
   uvicorn src.app:app --host 0.0.0.0 --port 80

   # Terminal 2 — Worker
   python worker.py
   ```

## Docker Build & Run

Build the container (multi-arch):
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t extralit/extralit-hf-spaces:<tag> \
  .
```

Run the container:
```bash
docker run -d \
  --name hf-space \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e ELASTICSEARCH_HOST=http://host.docker.internal:9200 \
  -p 80:80 \
  extralit/extralit-hf-spaces:<tag>
```

## Configuration / Environment Variables

- `REDIS_URL`  
  URL for Redis (default: `redis://redis:6379/0`).
- `ELASTICSEARCH_HOST`  
  Elasticsearch HTTP endpoint (default baked into container).
- `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OAUTH_SCOPES`  
  If deploying on HuggingFace Spaces for HF-OAuth integration.
- `USERNAME`, `PASSWORD`, `API_KEY`  
  HF Space owner credentials (used by `start.sh`).

## HTTP API

POST `/extract`

- Request: multipart/form-data with field `pdf` (application/pdf).  
- Response: JSON `{ "text": "<full extracted text>" }`.

Example:
```bash
curl -X POST http://localhost:80/extract \
  -F "pdf=@/path/to/sample.pdf" \
  -H "Content-Type: multipart/form-data"
```

## RQ Worker

Enqueue jobs in your Extralit server:

```python
from extralit_server.jobs.pymupdf_jobs import extract_text_remote

# file_bytes = open("doc.pdf","rb").read()
job = extract_text_remote.delay(file_bytes, document_id="1234")
# job.result -> returns extracted text when complete
```

Redis queue name: `pymupdf`

## License

This repository and container are licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).  
All AGPL-licensed code (PyMuPDF) remains fully contained here. Your main `extralit/extralit-server` codebase remains Apache-2.0.