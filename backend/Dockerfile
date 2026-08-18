FROM python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY src ./src
COPY scripts ./scripts
COPY generated_packages.100.json/migrate_package_companion_tags_50.sql ./generated_packages.100.json/migrate_package_companion_tags_50.sql
COPY data/raw/korea_tour_openapi_jeju_places.csv ./data/raw/korea_tour_openapi_jeju_places.csv
COPY data/raw/korea_tour_openapi_lcls_codes.csv ./data/raw/korea_tour_openapi_lcls_codes.csv
COPY data/processed/jeju_place_rag_documents.json ./data/processed/jeju_place_rag_documents.json
COPY data/processed/aihub ./data/processed/aihub

EXPOSE 8000

USER appuser

CMD ["gunicorn", "--chdir", "backend", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "config.wsgi:application"]
