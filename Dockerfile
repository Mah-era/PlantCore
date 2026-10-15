FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home plantcore
COPY app ./app
COPY web ./web
COPY examples ./examples
COPY test-files ./test-files
RUN mkdir -p /app/data && chown -R plantcore:plantcore /app
USER plantcore
ENV PLANTCORE_DB=/app/data/platform.db
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
