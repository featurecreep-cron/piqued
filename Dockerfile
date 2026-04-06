# Stage 1: Frontend build
FROM node:25-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python dependencies
FROM python:3.14-slim AS backend
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 3: Runtime
FROM python:3.14-slim

RUN groupadd -g 1000 piqued && useradd -u 1000 -g 1000 -d /app piqued
WORKDIR /app

COPY --from=backend /install /usr/local
COPY . .
COPY --from=frontend /build/dist /app/piqued/web/spa/

RUN mkdir -p /data && chown -R piqued:piqued /app /data

USER piqued

EXPOSE 8400

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8400/health')" || exit 1

CMD ["uvicorn", "piqued.main:app", "--host", "0.0.0.0", "--port", "8400", "--proxy-headers", "--forwarded-allow-ips=*"]
