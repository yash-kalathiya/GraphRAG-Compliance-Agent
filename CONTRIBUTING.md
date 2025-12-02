# Contributing to GraphRAG Legal Auditor

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Docker and Docker Compose
- Git

### Getting Started

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/graphrag-legal-auditor.git
   cd graphrag-legal-auditor
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   make dev-install
   # or manually:
   pip install -e ".[dev]"
   pre-commit install
   ```

4. **Start Neo4j**
   ```bash
   make docker-up
   ```

5. **Run tests to verify setup**
   ```bash
   make test
   ```

## Code Style

We use the following tools to maintain code quality:

- **Black** for code formatting
- **Ruff** for linting
- **mypy** for type checking

Run all checks with:
```bash
make check-all
```

### Style Guidelines

- Use type hints for all function signatures
- Write docstrings for all public functions, classes, and modules
- Keep functions focused and under 50 lines when possible
- Use meaningful variable names

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run only unit tests (no external dependencies)
make test-unit

# Run integration tests (requires Neo4j)
make test-integration
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Use pytest fixtures for common setup
- Mark tests appropriately:
  - `@pytest.mark.unit` - Fast tests without external deps
  - `@pytest.mark.integration` - Tests requiring Neo4j
  - `@pytest.mark.slow` - Long-running tests

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code following our style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Run checks locally**
   ```bash
   make check-all
   ```

4. **Commit with a descriptive message**
   ```bash
   git commit -m "feat: add support for PDF parsing"
   ```
   
   We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New features
   - `fix:` - Bug fixes
   - `docs:` - Documentation changes
   - `test:` - Test additions/changes
   - `refactor:` - Code refactoring

5. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Reporting Issues

When reporting issues, please include:

- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages

## Questions?

Feel free to open a Discussion for questions or reach out to the maintainers.

---

Thank you for contributing! 🎉
