# Agent-Farm: GitHub Copilot Instructions

You are a specialized GitHub Copilot agent for this repository. Follow these instructions exactly to handle onboarding, Context7 MCP, and the Serena MCP server so that Copilot can use them reliably.

## Quick Reference: Agent-Farm Technical Overview

**agent-farm** is a DuckDB-powered MCP Server providing SQL macros for LLM agents (web search, Python execution, RAG via SQL).

**Key Facts:**
- **Language:** Python 3.11+, Package Manager: **uv** (NOT pip), Database: DuckDB ≥1.1.0
- **Structure:** 190 lines main.py, 551 lines SQL macros, 2 test files (188 lines total)

---

## 1. Repository Onboarding Behavior

- On first use in this repo, always read:
  - `README.md`
  - `CONTRIBUTING.md`
  - Everything under `.github/` (especially `copilot-instructions.md`, `prompts/`, workflows).
- Prefer existing scripts and tasks for setup and builds:
  - Look for `Makefile`, `justfile`, `Taskfile.yml`, `package.json` scripts, or similar, and use those commands instead of inventing new ones.
- Before creating new files, services, MCP configs, or complex code:
  - Search the codebase for existing patterns and conventions.
  - Match the existing architecture, folder structure, naming, and coding style.
- When something is unclear in the repo:
  - State your assumptions briefly.
  - Propose concrete follow-up actions (for example "we should add X to `README.md`" or "this should be documented in `.github/copilot-instructions.md`").

## 2. Copilot Prompt Files for Onboarding

- This repo contains an onboarding prompt file based on GitHub's `onboarding-plan.prompt.md` pattern.
- **Location:** `.github/prompts/onboarding-plan.prompt.md`
- **The file contains:**
  - YAML front matter with `mode: 'agent'` and a descriptive `description`.
  - A Markdown body describing how to generate a phased onboarding plan for new contributors.
- **How to use:**
  - Open GitHub Copilot Chat in VS Code or JetBrains.
  - Invoke it with `/onboarding-plan` (or the actual filename prefix).
- **If adding new prompt files:**
  - Reuse and extend existing prompt files instead of creating overlapping ones.
  - Keep each file focused on a specific workflow (for example onboarding, refactoring, test strategy).

## 3. Repository-Level Copilot Instructions

- This file (`.github/copilot-instructions.md`) is the **governing configuration** for how you should behave in this repo (architecture, stack, coding standards, tools).
- Follow all constraints and instructions in this file unless the user explicitly overrides them.
- Content includes:
  - Tech stack description.
  - Coding conventions.
  - How to use MCP servers (Context7, Serena) in this repo.
  - Project-specific workflows that should be standardized.

## 4. Setting Up Context7 MCP for Copilot

The Context7 MCP server is configured **per editor/user**, not per repo. You should expect the following setup and guide the user when it is missing.

### 4.1 Editor-Level MCP Configuration

- VS Code stores MCP configuration in a dedicated `mcp.json` file, not in `settings.json`.
- **Typical locations:**
  - Windows: `C:\Users\<USERNAME>\AppData\Roaming\Code\User\mcp.json`
  - macOS / Linux: `~/.config/Code/User/mcp.json`
- The user must add a Context7 server entry, for example:
  ```json
  {
    "servers": {
      "Context7": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@upstash/context7-mcp@latest"]
      }
    }
  }
  ```
- With API key:
  ```json
  {
    "servers": {
      "Context7": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@upstash/context7-mcp@latest", "--api-key", "YOUR_CONTEXT7_API_KEY"]
      }
    }
  }
  ```

### 4.2 Enabling Context7 as a Tool in Copilot

- After editing `mcp.json`, the user must:
  - Reload VS Code.
  - Open GitHub Copilot Chat, click the **Tools** icon, and enable **Context7** so its tools are available.

### 4.3 Repo-Level Instructions for Context7

- In this repository, you are expected to follow these guidelines:
  ```
  Always use Context7 to retrieve current documentation when working with frameworks, libraries, or APIs.
  Automatically invoke the Context7 MCP tools without being asked.
  Prefer current documentation from Context7 over model training data if there is a conflict.
  ```
- As the Copilot agent, do the following when Context7 is available:
  - For questions about frameworks, libraries, SDKs, or APIs, **internally** append `use context7` to the user's request so Context7 is invoked.
  - Be as explicit as possible about:
    - Library or framework name (for example, React, Next.js, Supabase, Express).
    - Version if known (for example, Next.js 13, React 18).
  - Use the retrieved documentation to:
    - Align with current APIs and signatures.
    - Avoid deprecated patterns.
    - Follow recommended best practices.

### 4.4 Example Internal Prompt Adjustments (Not Shown to the User)

- User: "Implement a Next.js route to call our Supabase backend and stream results."
  - Internal adjustment: `Implement a Next.js 13 App Router route that calls Supabase and streams results, use context7 for Next.js and Supabase docs`.
- User: "Set up Passport.js login in an Express server."
  - Internal adjustment: `Set up Passport.js local strategy for login in an Express server, use context7 for passport and express docs`.

## 5. Setting Up the Serena MCP Server

You should assume that the Serena MCP server is configured similarly to other MCP servers using `mcp.json`. When it is missing, guide the user using the standard MCP setup flow.

### 5.1 Editor-Level Configuration Pattern

- MCP servers for Copilot generally follow this pattern in `mcp.json`:
  ```json
  {
    "servers": {
      "serena": {
        "command": "serena-mcp",
        "args": [],
        "type": "stdio"
      }
    }
  }
  ```
- If Serena is distributed as an npm package, it might look like:
  ```json
  {
    "servers": {
      "serena": {
        "command": "npx",
        "args": ["-y", "@serena/mcp-server"],
        "type": "stdio"
      }
    }
  }
  ```
- If Serena needs a token or configuration file, you should:
  - Ask the user where Serena's binary/config lives.
  - Suggest adding the appropriate `args` or environment variables to `mcp.json`.

### 5.2 Enabling Serena in Copilot Chat

- After Serena is added to `mcp.json`, the user must:
  - Reload the editor.
  - Open Copilot Chat, click the **Tools** icon, and ensure the **Serena** tools are enabled.

### 5.3 How You Should Use Serena as the Agent

- Use Serena when:
  - You need structured project analysis beyond simple text search (for example "find all call sites of function X across services").
  - You need to run complex repo-specific tools provided by Serena (for example project graph inspection, build diagnostics, domain-specific analyzers).
- When defining tasks that Serena should perform, think in terms of generic tool names so they can be mapped to Serena's implementation, for example:
  - "serena-read_file" – read files or file fragments.
  - "serena-search_code" – perform codebase-wide search.
  - "serena-analyze_graph" – run a structural or dependency analysis.
- If Serena is not available:
  - Say that explicitly.
  - Fall back to standard file search and pattern matching in the repo.

## 6. Using MCP with Copilot Agent Mode

- Copilot agent mode can use multiple MCP servers (Context7, Serena, GitHub MCP server, etc.) at the same time.
- Decision logic you should follow:
  - If the question is answerable purely from the current repo, prioritize reading the repo first.
  - If external documentation or API references are needed, use Context7.
  - If deeper structural analysis or repo-specific tools are needed, delegate those subtasks conceptually to Serena.

## 7. Repository-Specific Onboarding Workflow

- On first use in this repo, perform an internal onboarding pass:
  - Read `README.md`, `CONTRIBUTING.md`, and key files under `.github/`.
  - Build an internal mental model of:
    - Main services/modules.
    - Primary tech stack.
    - Expected development workflows (build, test, deploy).
- Offer to generate (if missing):
  - A short architecture and onboarding overview for new contributors.
  - A tailored `.github/copilot-instructions.md` describing how Copilot should behave here.
  - One or more `.github/prompts/*.prompt.md` files for recurring workflows (for example `/bugfix-guide`, `/refactor-module`, `/test-strategy`).

## 8. Answering Style

- Assume the user is a senior / lead engineer or software architect.
- Prefer:
  - Precise, concise technical language.
  - Concrete code examples and command lines.
  - Clear indication of assumptions and configuration requirements.
- If MCP servers (Context7 or Serena) appear misconfigured or unavailable:
  - Say what is missing (for example "Context7 MCP server is not listed in mcp.json").
  - Provide exact steps to fix it (file path, JSON snippet, and how to enable the tool in Copilot Chat).

---

## CRITICAL: Run These Commands (Validated, ~60sec first run)

```bash
# 1. ALWAYS FIRST: Install dependencies (if uv not found: pip install uv)
uv sync --dev

# 2. BEFORE COMMITTING: Lint and format (instant)
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# 3. BEFORE COMMITTING: Test (~4sec, expect tests to pass with warnings)
uv run pytest tests/ -v

# 4. Run server (optional)
uv run agent-farm  # or: uv run python -m agent_farm

# 5. Docker (may fail in sandboxed envs with cert errors - expected)
docker build -t agent-farm .
```

## Project Structure

```
agent-farm/
├── .github/
│   ├── workflows/          # CI/CD pipelines
│   │   ├── ci.yml         # Main CI: lint, test, docker, validate-macros
│   │   ├── security.yml   # CodeQL + dependency scan
│   │   ├── code-quality.yml
│   │   ├── dependencies.yml  # Weekly dependency updates
│   │   └── release.yml    # PyPI + Docker publish on tags
│   ├── instructions/       # File-specific coding guidelines
│   │   ├── python-source.instructions.md
│   │   ├── python-tests.instructions.md
│   │   ├── sql-macros.instructions.md
│   │   ├── docker.instructions.md
│   │   └── github-workflows.instructions.md
│   ├── agents/
│   │   └── devops-agent.md  # Specialized DevOps agent
│   ├── CONTRIBUTING.md
│   ├── WORKFLOWS.md        # Detailed workflow documentation
│   └── copilot-instructions.md  # This file
├── src/agent_farm/
│   ├── __init__.py
│   ├── main.py            # 190 lines: Entry point, extension loading, MCP server
│   ├── macros.sql         # 551 lines: SQL macros for LLM integration
│   └── py.typed
├── tests/
│   ├── test_macros.py     # 137 lines: Main test with SQL parser helper
│   └── verify_farm.py     # 51 lines: Verification script
├── scripts/
│   ├── install_extensions.py  # Pre-install DuckDB extensions
│   └── test_extensions.py     # Test extension availability
├── pyproject.toml         # Project metadata, dependencies, ruff config
├── uv.lock               # Locked dependencies
├── Dockerfile            # Multi-stage Python 3.11-slim build
├── mcp.json.example      # Template for editor MCP config
└── README.md             # User-facing documentation
```

## Key Files by Purpose

### Making Code Changes
- **Python code:** `src/agent_farm/main.py` (extensions, MCP tables, server startup)
- **SQL macros:** `src/agent_farm/macros.sql` (Ollama, web search, shell, RAG, etc.)
- **Tests:** `tests/test_macros.py` (uses `split_sql_statements()` helper)

### Configuration
- **Dependencies:** `pyproject.toml` (requires-python = ">=3.11", line-length = 100)
- **Linter config:** `[tool.ruff]` section in pyproject.toml (target-version = "py311")
- **Package manager:** `uv.lock` (locked versions, don't edit manually)
- **Docker:** `Dockerfile` (Python 3.11-slim, uv for package management)

### Documentation
- **User guide:** `README.md` (features, installation, usage examples)
- **Contributing:** `.github/CONTRIBUTING.md` (dev setup, branching, commit messages)
- **Workflows:** `.github/WORKFLOWS.md` (detailed CI/CD documentation)
- **Instructions:** `.github/instructions/*.instructions.md` (file-type-specific rules)

## CI/CD Pipelines (GitHub Actions)

### CI Workflow (`.github/workflows/ci.yml`)
**Triggers:** Push to main/master, PRs, manual dispatch
**Jobs:**
1. **lint:** Ruff check + format check (uses uv cache)
2. **test:** pytest on Python 3.11 & 3.12 (matrix build, uses uv cache)
3. **docker:** Docker build (uses GitHub Actions cache)
4. **validate-macros:** Run test_macros.py (uses uv cache)

**Critical:** All jobs use uv dependency caching with `uv.lock` hash as key. Cache path: `~/.cache/uv`

### Security Workflow (`.github/workflows/security.yml`)
**Triggers:** Push, PR, weekly (Monday 00:00 UTC), manual
**Jobs:**
1. **codeql:** Static analysis (skips PRs to reduce redundancy)
2. **dependency-scan:** pip-audit on dependencies
3. **docker-scan:** Trivy scan (skips PRs unless labeled 'security')

### Other Workflows
- **code-quality.yml:** Radon complexity, coverage, markdown links, file structure
- **dependencies.yml:** Weekly updates (Monday 08:00 UTC), creates PRs
- **release.yml:** Triggered by tags matching `v*.*.*`, publishes to PyPI + GHCR

## Common Pitfalls

1. **"Command 'uv' not found"** → `pip install uv` first
2. **"No module named 'ruff'"** → Run `uv sync --dev` (NOT just `uv sync`)
3. **Docker cert errors** → Expected in sandboxed envs, don't fix
4. **Extension load failures** → Normal for `radio`, `shellfs`; tests auto-skip
5. **Test warning "returning non-None"** → Harmless, tests still pass

## Coding Standards (CRITICAL)

**Python** (`src/agent_farm/*.py`): 100 char lines (STRICT), Ruff E/F/I/W rules, type hints for public APIs, print errors to stderr
**SQL Macros** (`src/agent_farm/macros.sql`): Always `CREATE OR REPLACE MACRO`, use `TRY()` for safety, `http_get()`/`http_post()` for HTTP, `json_extract_string()` for JSON
**Tests** (`tests/*.py`): pytest with `:memory:` DB, try-except for extensions, mock external APIs
**Workflows** (`.github/workflows/*.yml`): Cache uv deps with `uv.lock` hash, cancel in-progress runs, minimal permissions

## Making Changes (Pre-Commit Checklist)

```bash
uv sync --dev                              # 1. Update deps
uv run ruff format src/ tests/             # 2. Format
uv run ruff check --fix src/ tests/        # 3. Lint
uv run pytest tests/ -v                    # 4. Test (ensure all tests pass)
# Then commit - CI will run same checks
```

**SQL Macro:** Edit `src/agent_farm/macros.sql` → Use `CREATE OR REPLACE MACRO` → Test → Update README if user-facing
**Python Code:** Edit `src/agent_farm/main.py` → 100 char lines, type hints, try-except → Test → Lint → Format
**Workflow:** Edit `.github/workflows/*.yml` → Add concurrency + caching + manual trigger → Update `.github/WORKFLOWS.md`

## Quick Reference

**Deps:** `uv sync --dev` | **Lint:** `uv run ruff check --fix src/ tests/` | **Format:** `uv run ruff format src/ tests/`
**Test:** `uv run pytest tests/ -v` | **Run:** `uv run agent-farm` | **Add pkg:** `uv add pkg-name`

**Remember:** (1) Run `uv sync --dev` first, (2) Use uv not pip, (3) 100 char line limit, (4) Python 3.11+, (5) Test before commit

**More info:** `.github/CONTRIBUTING.md`, `.github/WORKFLOWS.md`, `.github/instructions/*.instructions.md`
