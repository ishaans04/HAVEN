# HAVEN — one container, one port.
#
# The console is a static export served by FastAPI from the same origin as the
# API, so there is one process to start and nothing to configure. That is the
# difference between a reviewer visiting a URL and a reviewer debugging a
# virtualenv.
#
# Two stages: Node builds the console, Python runs everything. Node does not
# survive into the final image.

# --------------------------------------------------------------------------
# Stage 1 — build the console
# --------------------------------------------------------------------------
FROM node:20-slim AS console

WORKDIR /build

# Dependencies first, so a source change does not re-resolve the tree.
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./

# The generated contract types are committed, and CI fails if they have drifted
# from openapi.json, so the image builds from the same bytes that were reviewed
# rather than regenerating them here.
ENV NEXT_TELEMETRY_DISABLED=1
# Empty means same-origin, which is what this image serves.
ENV NEXT_PUBLIC_API_BASE=""
RUN npm run build


# --------------------------------------------------------------------------
# Stage 2 — the engine, and the console it serves
# --------------------------------------------------------------------------
FROM python:3.12-slim

# Never phone home. haven/offline.py clears these at import as well; setting
# them here means a container that somehow never reaches Python is still quiet.
ENV LANGCHAIN_TRACING_V2=false \
    LANGSMITH_TRACING=false \
    ANONYMIZED_TELEMETRY=False \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies before source, so editing a module does not reinstall the tree.
# --frozen: the lockfile is the build, and resolving afresh in a container would
# make the image differ from what was tested.
#
# No extras. The base install is the offline path, and an image that needed
# watsonx credentials or a model download to start would not be one.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY haven/ ./haven/
COPY scripts/ ./scripts/
COPY evaluation/ ./evaluation/
COPY openapi.json README.md CHANGELOG.md ./

COPY --from=console /build/out ./web/out

# The ledger and its signing key are generated on first run. A volume here keeps
# an audit trail across restarts; without one the container is still correct,
# just amnesiac -- which is the right default for a demo and the wrong one for
# anything real.
ENV HAVEN_LEDGER_DB=/data/haven_ledger.db \
    HAVEN_AUDIT_KEY_FILE=/data/.audit_key
RUN mkdir -p /data
VOLUME ["/data"]

# 7860 is what Hugging Face Spaces expects.
ENV PORT=7860
EXPOSE 7860

# A non-root user, and /data owned by it so the key can be written.
RUN useradd --create-home --uid 1000 haven && chown -R haven:haven /app /data
USER haven

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health').read()"

CMD ["sh", "-c", "uv run --no-dev uvicorn haven.api.main:app --host 0.0.0.0 --port ${PORT}"]
