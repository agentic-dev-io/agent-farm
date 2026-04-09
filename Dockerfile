# Agent Farm — DuckDB Spec-OS for multi-org AI agent swarms
# Multi-stage build: Chainguard Python for zero-CVE runtime.

# -------- Builder stage --------
# Chainguard dev image ships with uv, gcc and apk preinstalled.
FROM cgr.dev/chainguard/python:latest-dev AS builder

USER root
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
COPY scripts/ scripts/
COPY tests/ tests/

ARG INSTALL_DEV=0
RUN if [ "$INSTALL_DEV" = "1" ]; then uv sync --frozen --all-extras; else uv sync --frozen --no-dev; fi

# Pre-install DuckDB extensions (cached under /root/.duckdb/extensions)
RUN /app/.venv/bin/python scripts/install_extensions.py

# Stage the data volume directory with nonroot ownership so the runtime image
# (which has no shell) can expose it without a RUN step.
RUN mkdir -p /stage/data /stage/home/nonroot \
    && cp -a /root/.duckdb /stage/home/nonroot/.duckdb \
    && chown -R 65532:65532 /stage

# -------- Runtime stage --------
# Minimal Chainguard Python image: no shell, no package manager, nonroot by default.
FROM cgr.dev/chainguard/python:latest AS runtime

WORKDIR /app

COPY --from=builder --chown=65532:65532 /app /app
COPY --from=builder --chown=65532:65532 /stage/home/nonroot/.duckdb /home/nonroot/.duckdb
COPY --from=builder --chown=65532:65532 /stage/data /data

VOLUME /data
ENV DUCKDB_DATABASE=/data/farm.db
ENV PATH="/app/.venv/bin:$PATH"

USER nonroot
EXPOSE 8080

ENTRYPOINT ["/app/.venv/bin/agent-farm"]
CMD ["mcp"]
