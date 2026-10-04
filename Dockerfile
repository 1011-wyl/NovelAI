# ---- frontend build ----
FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

# ---- python runtime ----
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY novel_agent ./novel_agent
COPY apps ./apps
COPY vendor ./vendor
COPY --from=frontend /web/dist ./apps/web/dist
RUN pip install --no-cache-dir .

ENV NOVEL_AGENT_HOST=0.0.0.0
ENV NOVEL_AGENT_PORT=8000
EXPOSE 8000
CMD ["python", "-m", "novel_agent", "serve"]
