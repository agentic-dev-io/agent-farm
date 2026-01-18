---
applyTo: "**/Dockerfile*"
---

## Docker Configuration Guidelines

When creating or modifying Dockerfiles in the agent-farm repository, follow these standards for security, performance, and maintainability:

### Base Image Selection

1. **Python version** - Use `python:3.11-slim` as the base image for smaller size
2. **Official images** - Always use official Python images from Docker Hub
3. **Version pinning** - Consider pinning specific Python patch versions for reproducibility
4. **Slim variants** - Prefer `-slim` variants to minimize image size

### Multi-Stage Builds

1. **Consider multi-stage** - Use multi-stage builds if building from source with compile dependencies
2. **Separate concerns** - Keep build dependencies separate from runtime dependencies
3. **Minimal runtime** - Only copy necessary artifacts to final image

### System Dependencies

1. **Essential only** - Install only required system packages
2. **Clean up** - Remove apt lists after installation: `rm -rf /var/lib/apt/lists/*`
3. **Single RUN command** - Combine apt-get commands to minimize layers:
   ```dockerfile
   RUN apt-get update && apt-get install -y \
       build-essential \
       curl \
       && rm -rf /var/lib/apt/lists/*
   ```

### UV Package Manager

1. **Binary installation** - Copy uv binary from official image:
   ```dockerfile
   COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
   ```
2. **Frozen installs** - Use `uv sync --frozen --no-dev` for production builds
3. **Lock file** - Always include `uv.lock` in the image
4. **Virtual environment** - UV creates `.venv` automatically, add to PATH

### DuckDB Extension Handling

1. **Pre-install extensions** - Run extension installation script during build
2. **Error handling** - Handle unavailable extensions gracefully in install script
3. **Extension caching** - Consider caching extension downloads to speed up builds
4. **Script location** - Use dedicated `scripts/install_extensions.py` for extension setup

### Security Best Practices

1. **Non-root user** - Always create and switch to non-root user:
   ```dockerfile
   RUN useradd -m farmer
   USER farmer
   ```
2. **Minimal permissions** - Set appropriate file permissions
3. **No secrets** - Never include secrets or credentials in Dockerfile
4. **Scan images** - Use security scanning tools on built images

### File Organization

1. **Working directory** - Set clear WORKDIR (e.g., `/app`)
2. **Copy order** - Copy dependency files before source code to leverage caching:
   ```dockerfile
   COPY pyproject.toml uv.lock ./
   RUN uv sync --frozen --no-dev
   COPY src/ src/
   ```
3. **Source structure** - Maintain the same directory structure as the repository

### Volume & Data Management

1. **Data directory** - Create dedicated directory for persistent data: `/data`
2. **Volume definition** - Use VOLUME directive for data directories
3. **Ownership** - Set correct ownership for volume mount points
4. **Environment variables** - Use ENV for configurable paths (e.g., `DB_PATH=/data/farm.db`)

### Port Configuration

1. **EXPOSE directive** - Document exposed ports even if not strictly required
2. **Standard ports** - Use standard ports when applicable (8080 for HTTP)
3. **Configuration** - Allow port configuration via environment variables

### Command & Entrypoint

1. **CMD format** - Use JSON array format: `CMD ["python", "-m", "agent_farm"]`
2. **Module execution** - Use `-m` flag for module execution
3. **Entrypoint** - Consider ENTRYPOINT for fixed commands, CMD for default arguments
4. **Signal handling** - Ensure proper signal handling for graceful shutdown

### Environment Variables

1. **Path configuration** - Add virtual environment to PATH:
   ```dockerfile
   ENV PATH="/app/.venv/bin:$PATH"
   ```
2. **Database path** - Set default database path
3. **Python settings** - Consider `PYTHONUNBUFFERED=1` for logging

### Build Optimization

1. **Layer caching** - Order commands to maximize Docker layer caching
2. **Minimal rebuilds** - Copy dependency files first, source code last
3. **Build context** - Use `.dockerignore` to exclude unnecessary files
4. **Image size** - Regularly check and optimize final image size

### Testing & Validation

1. **Build locally** - Test Docker builds locally before committing:
   ```bash
   docker build -t agent-farm:test .
   ```
2. **Run container** - Verify container starts and runs correctly:
   ```bash
   docker run -v /tmp/data:/data agent-farm:test
   ```
3. **Check size** - Monitor image size: `docker images agent-farm:test`
4. **Scan for vulnerabilities** - Use Docker scan or similar tools

### Multi-Platform Support

1. **Platform specification** - Consider supporting multiple platforms (amd64, arm64)
2. **Buildx** - Use Docker Buildx for multi-platform builds
3. **Testing** - Test on target platforms when possible

### Example Dockerfile Pattern

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ src/
COPY scripts/ scripts/
COPY README.md .

# Pre-install DuckDB extensions (using python from venv)
RUN .venv/bin/python scripts/install_extensions.py

# Create non-root user and data directory
RUN useradd -m farmer && \
    mkdir -p /data && \
    chown farmer:farmer /data

VOLUME /data
ENV DB_PATH=/data/farm.db
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER farmer

EXPOSE 8080

CMD ["python", "-m", "agent_farm"]
```

### Documentation

When modifying Dockerfile:
1. Update README.md with any new build arguments or environment variables
2. Document required system dependencies
3. Update Docker-related CI/CD workflows if needed
4. Maintain comments in Dockerfile explaining non-obvious choices
