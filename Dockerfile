# syntax=docker/dockerfile:1

FROM node:20-bookworm-slim AS frontend

WORKDIR /app/viewer/frontend
COPY viewer/frontend/package*.json ./
RUN npm ci
COPY viewer/frontend ./
RUN npm run build


FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    CLINICAL_HARNESS_RUNS=/data/runs \
    CLINICAL_VIEWER_USER_GENERATED=/data/user_generated

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY viewer/backend ./viewer/backend
COPY viewer/ARCHITECTURE.md viewer/README.md ./viewer/
COPY --from=frontend /app/viewer/frontend/dist ./viewer/frontend/dist

RUN pip install --no-cache-dir -e . -e viewer/backend \
    && mkdir -p /data/runs /data/user_generated

EXPOSE 10000

CMD ["sh", "-c", "uvicorn clinical_viewer.app:app --host 0.0.0.0 --port ${PORT:-10000}"]
