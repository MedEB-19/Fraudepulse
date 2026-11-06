FROM python:3.11-slim

RUN groupadd -r dashgroup && useradd -r -g dashgroup dashuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p .streamlit && \
    chown -R dashuser:dashgroup /app

USER dashuser

EXPOSE 8501

CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
