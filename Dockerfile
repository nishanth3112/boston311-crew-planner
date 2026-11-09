# One container: FastAPI serves the API and the built web app on port 8000.
#   docker build -t boston311 .
#   docker run --env-file .env -p 8000:8000 boston311

# --- web: build web/dist (uses the committed src/api/schema.d.ts, so no Python here) ---
FROM node:26-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- app ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# dependencies first, so code changes don't reinstall them
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY data/processed ./data/processed
# editable install (uv's default): config.ROOT must resolve to /app, where data/ lives
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist ./web/dist

# download the embedding model and build the intake search index now, not on the first request
RUN uv run --no-sync python -c "from boston311.genai.retriever import search; search('pothole')"

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "boston311.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
