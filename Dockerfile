# NetCable — single image (UI + API on one port).
# docker build -t netcable . && docker run -p 8080:8080 -v netcable-data:/app/data netcable

# 1) Build the UI (React/Vite)
FROM node:20-alpine AS interface
WORKDIR /src
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Server (FastAPI) serving the API and the UI
FROM python:3.11-slim
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="NetCable" \
      org.opencontainers.image.description="Open-source, self-hosted network map & monitoring" \
      org.opencontainers.image.source="https://github.com/Joao-Monticelli/NetCable-v1" \
      org.opencontainers.image.version="${APP_VERSION}"
ENV APP_VERSION=${APP_VERSION} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NETCABLE_DATA_DIR=/app/data \
    NETCABLE_STATIC_DIR=/app/static
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=interface /src/dist ./static
VOLUME ["/app/data"]
EXPOSE 8080
# PORT only matters with network_mode: host (to avoid clashing with something already on 8080).
ENV PORT=8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3   CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8080'), timeout=4).status == 200 else 1)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8080}\" --proxy-headers"]
