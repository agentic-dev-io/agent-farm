# Dockerfile for farmer_agent with DuckDB extensions
# Use this if radio or other extensions fail to load on Windows

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for DuckDB extensions
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY README.md .
COPY install_extensions.py .

# Install dependencies using uv sync
RUN uv sync --frozen --no-dev

# Pre-install DuckDB extensions (with error handling for unavailable extensions)
RUN /app/.venv/bin/python install_extensions.py

# Create a non-root user
RUN useradd -m farmer
RUN mkdir -p /data && chown farmer:farmer /data
VOLUME /data
ENV DB_PATH=/data/farm.db

# Switch to non-root user
USER farmer

# Add venv to path
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

CMD ["python", "-m", "agent_farm"]
