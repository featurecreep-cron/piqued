FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

RUN groupadd -g 1000 piqued && useradd -u 1000 -g 1000 -d /app piqued
WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

RUN mkdir -p /data && chown -R piqued:piqued /app /data

USER piqued

EXPOSE 8400

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8400/health')" || exit 1

CMD ["uvicorn", "piqued.main:app", "--host", "0.0.0.0", "--port", "8400"]
