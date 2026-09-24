# ============================================================
# DOCKERFILE — E-Commerce BI & SQL Analytics System (API)
# ============================================================
# Multi-stage: builder installs deps, runtime stays lean.
# ============================================================

FROM python:3.10.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements_api.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements_api.txt


FROM python:3.10.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project source
COPY src/        ./src/
COPY serving/    ./serving/
COPY services/   ./services/
COPY artifacts/  ./artifacts/
COPY logs/       ./logs/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

CMD ["uvicorn", "serving.ecommerce_api:app", "--host", "0.0.0.0", "--port", "8000"]
