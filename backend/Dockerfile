FROM python:3.11-slim

WORKDIR /app

# System deps for any future Maven/Spark needs in later slices; minimal for now.
RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*

# Copy package metadata first to leverage Docker layer cache for deps.
COPY pyproject.toml /app/
COPY backend/ /app/backend/

RUN pip install --no-cache-dir -e ".[runtime]"

# Pre-warm bge model into the image (~25MB)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
