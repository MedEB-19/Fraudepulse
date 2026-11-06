# Build context = repo root (needs src/fraudpulse for the shared feature code)
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY src/model_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/fraudpulse /app/src/fraudpulse
COPY src/model_server /app/src/model_server
ENV PYTHONPATH=/app/src:/app/src/model_server
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
