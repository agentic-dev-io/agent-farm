---
applyTo: ".github/workflows/*.yml"
---

## GitHub Actions Workflow Guidelines

When creating or modifying GitHub Actions workflows in the agent-farm repository, follow these best practices for reliability, performance, and maintainability:

### Workflow Structure

1. **Naming** - Use clear, descriptive workflow names that reflect their purpose
2. **Triggers** - Explicitly define when workflows should run (push, pull_request, schedule, workflow_dispatch)
3. **Concurrency** - Use concurrency groups to cancel in-progress runs:
   ```yaml
   concurrency:
     group: ${{ github.workflow }}-${{ github.ref }}
     cancel-in-progress: true
   ```
4. **Manual triggers** - Include `workflow_dispatch:` for manual execution when appropriate

### Job Organization

1. **Job names** - Use descriptive names that clearly indicate purpose
2. **Matrix strategy** - Use matrix builds for testing multiple Python versions (3.11, 3.12)
3. **Dependencies** - Use `needs:` to define job dependencies
4. **Fail-fast** - Set `fail-fast: false` for matrix builds to see all failures

### Performance Optimization

1. **Caching** - Always cache uv dependencies:
   ```yaml
   - name: Cache uv dependencies
     uses: actions/cache@v4
     with:
       path: ~/.cache/uv  # Linux/macOS. Windows uses ~\AppData\Local\uv
       key: ${{ runner.os }}-uv-${{ hashFiles('**/uv.lock') }}
       restore-keys: |
         ${{ runner.os }}-uv-
   ```
2. **Docker caching** - Use GitHub Actions cache for Docker builds:
   ```yaml
   cache-from: type=gha
   cache-to: type=gha,mode=max
   ```
3. **Parallel jobs** - Run independent jobs in parallel
4. **Minimal checkouts** - Only checkout code when needed

### Standard Steps for Python Jobs

1. **Checkout** - Use `actions/checkout@v4`
2. **Python setup** - Use `actions/setup-python@v5` with explicit version
3. **Install uv** - Use `astral-sh/setup-uv@v4` with version "latest"
4. **Cache dependencies** - Cache uv dependencies as shown above
5. **Install dependencies** - Run `uv sync --dev` for development dependencies

### Security Best Practices

1. **Pin action versions** - Use specific versions for actions (e.g., `@v4`, not `@latest`)
2. **Minimal permissions** - Use principle of least privilege for tokens
3. **Secret handling** - Use GitHub Secrets for sensitive values, never hardcode
4. **Token scoping** - Use `${{ secrets.GITHUB_TOKEN }}` with minimal required permissions

### Testing & Quality

1. **Linting first** - Run linting before tests to fail fast
2. **Multiple Python versions** - Test on both Python 3.11 and 3.12
3. **Test reporting** - Add test summaries to `$GITHUB_STEP_SUMMARY`
4. **Failure handling** - Use `if: always()` for cleanup or reporting steps

### Docker Workflows

1. **Buildx setup** - Use `docker/setup-buildx-action@v3`
2. **Multi-platform** - Consider building for multiple architectures if needed
3. **Image tagging** - Use semantic versioning for release images
4. **Registry authentication** - Handle authentication securely for pushing images

### Environment Variables

1. **UV settings** - No special UV_ environment variables required for basic usage
2. **Python environment** - Set `PYTHONUNBUFFERED=1` for real-time logging
3. **DuckDB paths** - Use environment variables for database paths when needed

### Error Handling

1. **Continue on error** - Use `continue-on-error: true` sparingly and intentionally
2. **Failure notifications** - Consider adding notifications for critical workflow failures
3. **Retry logic** - Use retry actions for flaky external dependencies

### Documentation & Maintenance

1. **Comments** - Add comments explaining complex workflow logic
2. **Version updates** - Regularly update action versions
3. **Deprecation warnings** - Address GitHub Actions deprecation warnings promptly
4. **Workflow documentation** - Keep `.github/WORKFLOWS.md` updated

### Example Workflow Job

```yaml
lint:
  name: Lint Code
  runs-on: ubuntu-latest
  steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install uv
      uses: astral-sh/setup-uv@v4
      with:
        version: "latest"

    - name: Cache uv dependencies
      uses: actions/cache@v4
      with:
        path: ~/.cache/uv
        key: ${{ runner.os }}-uv-${{ hashFiles('**/uv.lock') }}
        restore-keys: |
          ${{ runner.os }}-uv-

    - name: Install dependencies
      run: uv sync --dev

    - name: Run Ruff linter
      run: uv run ruff check src/ tests/

    - name: Check code formatting
      run: uv run ruff format --check src/ tests/
```

### Workflow-Specific Guidelines

#### CI Workflow
- Run on all pushes and PRs to main/master
- Include linting, testing, Docker build, and macro validation
- Use matrix testing for Python versions

#### Security Workflow
- Run on pushes, PRs, and weekly schedule
- Include CodeQL analysis and dependency scanning
- Report security findings

#### Release Workflow
- Trigger on version tags (v*)
- Build and publish to PyPI
- Create GitHub releases with changelog
- Build and push Docker images

#### Dependencies Workflow
- Run weekly to check for updates
- Use Dependabot or similar for automation
- Test compatibility before auto-merging

### Testing Locally

Before pushing workflow changes:
```bash
# Validate YAML syntax
yamllint .github/workflows/*.yml

# Test the commands locally
uv sync --dev
uv run ruff check src/ tests/
uv run pytest tests/ -v
docker build -t agent-farm:test .
```
