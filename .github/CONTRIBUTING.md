# Contributing to Agent Farm

Thank you for your interest in contributing to Agent Farm! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [DevOps and CI/CD](#devops-and-cicd)

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/agent-farm.git
   cd agent-farm
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/bjoernbethge/agent-farm.git
   ```

## Development Setup

### Prerequisites
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git
- Docker (optional, for container testing)

### Installation

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync --dev

# Verify installation
uv run agent-farm --help
```

### IDE Setup

#### VS Code
Install recommended extensions:
- Python
- Ruff
- GitHub Copilot (optional)

The repository includes Copilot instructions in `.github/copilot-instructions.md`.

#### PyCharm
Configure Python interpreter to use the virtual environment created by uv.

## Making Changes

### Branching Strategy

Create a feature branch from `main`:
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation changes
- `refactor/*` - Code refactoring
- `test/*` - Test additions or modifications

### Development Workflow

1. **Make your changes** in the appropriate files
2. **Add tests** for new functionality
3. **Run tests locally**:
   ```bash
   uv run pytest tests/ -v
   ```
4. **Run linter**:
   ```bash
   uv run ruff check --fix src/ tests/
   uv run ruff format src/ tests/
   ```
5. **Commit your changes** (see commit message guidelines below)
6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_macros.py

# Run with verbose output
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=agent_farm --cov-report=html
```

### Writing Tests

Tests should be added to the `tests/` directory:

```python
import duckdb
import pytest

def test_new_feature():
    """Test description"""
    con = duckdb.connect(':memory:')
    
    # Load necessary extensions
    con.sql("INSTALL httpfs; LOAD httpfs;")
    
    # Test your feature
    result = con.sql("SELECT your_macro('input')").fetchone()
    
    assert result is not None
    assert result[0] == "expected_output"
```

### Test Guidelines
- Test both success and failure cases
- Use descriptive test names
- Keep tests independent
- Mock external dependencies
- Test edge cases

## Code Style

### Python Style Guide

We use **Ruff** for linting and formatting:

- **Line length**: 100 characters
- **Naming**: 
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Imports**: Organized automatically by Ruff
- **Type hints**: Use for public APIs

### SQL Style

For SQL macros in `macros.sql`:

```sql
-- Clear description of what the macro does
-- param1: Description of parameter
CREATE OR REPLACE MACRO macro_name(param1, param2) AS (
    SELECT ...
);
```

Guidelines:
- Use uppercase for SQL keywords
- Use lowercase for identifiers
- Indent nested queries
- Add comments for complex logic

### Documentation

- **Docstrings**: Use for all public functions/classes
- **Comments**: Explain "why", not "what"
- **README**: Update if adding user-facing features
- **Type hints**: Add to function signatures

Example:
```python
def process_data(input_data: str) -> dict:
    """
    Process input data and return structured result.
    
    Args:
        input_data: Raw input string to process
        
    Returns:
        Dictionary containing processed data
        
    Raises:
        ValueError: If input_data is empty
    """
    if not input_data:
        raise ValueError("input_data cannot be empty")
    # Implementation...
```

## Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

### Examples
```bash
feat(macros): add semantic search macro using VSS extension

fix(server): handle missing MCP config gracefully

docs(readme): update installation instructions for uv

test(macros): add tests for ollama chat integration

chore(deps): update duckdb to 1.1.1
```

## Pull Request Process

### Before Submitting

1. ✅ All tests pass locally
2. ✅ Linting passes
3. ✅ Code is formatted
4. ✅ Documentation updated (if needed)
5. ✅ Commit messages follow convention
6. ✅ Branch is up-to-date with main

### Submitting a PR

1. **Push your branch** to your fork
2. **Create a pull request** on GitHub
3. **Fill out the PR template** with:
   - Description of changes
   - Related issue numbers
   - Testing performed
   - Breaking changes (if any)

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] All tests pass locally
- [ ] Added new tests for changes
- [ ] Manually tested functionality

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings generated
```

### Review Process

1. Automated checks run (CI, security, quality)
2. Maintainer reviews code
3. Address feedback if requested
4. Approval and merge

## DevOps and CI/CD

### GitHub Actions Workflows

The repository uses automated workflows for:
- **CI**: Linting, testing, Docker builds
- **Security**: CodeQL, dependency scanning
- **Quality**: Code complexity, coverage
- **Dependencies**: Automated updates
- **Release**: PyPI and Docker publishing

See [WORKFLOWS.md](.github/WORKFLOWS.md) for details.

### Specialized DevOps Agent

For DevOps-related contributions, consult the specialized agent documentation:
- [DevOps Agent](.github/agents/devops-agent.md)

### Working with Workflows

Test workflow changes in your fork:
```bash
# Push to your fork
git push origin feature/workflow-update

# GitHub Actions will run in your fork
# Review results before creating PR
```

### Docker Development

```bash
# Build image locally
docker build -t agent-farm:dev .

# Run container
docker run -it --rm agent-farm:dev

# Test with mounted data
docker run -v $(pwd)/data:/data agent-farm:dev
```

## MCP Memory Integration

When working on features that use MCP memory:

1. Update `mcp.json` configuration
2. Add/update tables in `setup_mcp_tables()`
3. Document new memory structures
4. Test memory persistence

Example:
```python
def setup_agent_memory(con):
    """Setup tables for agent memory storage"""
    con.sql("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            key VARCHAR PRIMARY KEY,
            value JSON,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
```

## Getting Help

- **Issues**: Check existing issues or create a new one
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Refer to README and inline documentation

## Recognition

Contributors will be recognized in:
- GitHub contributors list
- Release notes for significant contributions
- Project documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Agent Farm! 🚜🦆
