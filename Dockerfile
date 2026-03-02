FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OPENDTU_DB_PATH=/app/data/opendtu_stats.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY collect.py dashboard.py ./
COPY opendtu_stats ./opendtu_stats
COPY docker ./docker

RUN chmod +x /app/docker/collector-loop.sh

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "dashboard.py", "--server.headless", "true", "--server.address", "0.0.0.0", "--server.port", "8501"]
