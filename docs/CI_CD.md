# CI/CD Pipeline Documentation

This document describes the CI/CD pipeline configuration for the piyasa_chat_bot project.

## Overview

The project uses **GitHub Actions** for continuous integration and continuous deployment. The pipeline consists of three main workflows:

1. **Tests & Code Quality** (`test.yml`) - Automated testing, linting, and coverage
2. **Docker Build & Push** (`docker-build.yml`) - Container image building and publishing
3. **CodeQL Security Scanning** (`codeql.yml`) - Automated security analysis

## Workflows

### 1. Tests & Code Quality (`test.yml`)

**Triggers**:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual dispatch

**Jobs**:

#### a. Lint (Code Quality Checks)
- **black**: Code formatting check
- **isort**: Import sorting check
- **flake8**: Linting and style check
- **bandit**: Security vulnerability scanning

#### b. Test (Run Tests)
- **Matrix**: Python 3.11 and 3.12
- **pytest** with coverage
- **Redis** service for integration tests
- **Coverage report** upload to Codecov

#### c. Integration Test
- Docker Compose service startup
- Preflight health checks
- Integration test suite

#### d. Summary
- Aggregate test results
- Fail if any critical tests fail

**Environment Variables**:
```yaml
API_KEY: test-api-key-for-ci
TOKEN_ENCRYPTION_KEY: <base64-test-key>
OPENAI_API_KEY: sk-test-key-not-real
DATABASE_URL: sqlite:///./test.db
REDIS_URL: redis://localhost:6379/0
```

**Artifacts**:
- Test results (pytest-report.xml)
- Coverage reports (coverage.xml, htmlcov/)
- Security reports (bandit-report.json)

---

### 2. Docker Build & Push (`docker-build.yml`)

**Triggers**:
- Push to `main` branch
- Version tags (`v*.*.*`)
- Pull requests to `main`
- Manual dispatch

**Jobs**:

#### a. Build API
- Multi-architecture build (amd64, arm64)
- Push to GitHub Container Registry (ghcr.io)
- Tagging strategy:
  - `latest` (main branch)
  - `v1.2.3` (semantic versioning)
  - `main-<sha>` (commit hash)
  - `pr-123` (pull request number)

#### b. Build Frontend
- Same as API but for frontend image

#### c. Security Scan
- **Trivy** vulnerability scanner
- SARIF report upload to GitHub Security
- Artifact retention: 90 days

#### d. Test Image
- Pull built images
- Start containers
- Verify containers run successfully

**Container Registry**: `ghcr.io/uzaktantakip000-create/piyasa_chat_bot`

**Images**:
- `ghcr.io/.../piyasa_chat_bot/api:latest`
- `ghcr.io/.../piyasa_chat_bot/frontend:latest`

---

### 3. CodeQL Security Scanning (`codeql.yml`)

**Triggers**:
- Push to `main` or `develop`
- Pull requests
- Schedule: Every Sunday at 02:00 UTC
- Manual dispatch

**Languages Analyzed**:
- Python
- JavaScript

**Queries**:
- Security-extended
- Security-and-quality

**Results**:
- Uploaded to GitHub Security tab
- Alerts created for vulnerabilities

---

## Configuration Files

### Test Configuration

**pytest.ini** - Pytest settings:
```ini
[pytest]
testpaths = tests
addopts = -v --strict-markers --cov=. --cov-report=term-missing
markers = slow, integration, unit, api, engine
```

**.coveragerc** - Coverage settings:
```ini
[run]
source = .
branch = true
omit = */tests/*, */venv/*, */__pycache__/*

[report]
precision = 2
show_missing = true
```

### Linting Configuration

**.flake8** - Flake8 linter:
```ini
[flake8]
max-line-length = 120
max-complexity = 15
ignore = E203, W503, E501
```

**pyproject.toml** - Black & isort:
```toml
[tool.black]
line-length = 120
target-version = ['py311', 'py312']

[tool.isort]
profile = "black"
line_length = 120
```

### Development Requirements

**requirements-dev.txt**:
- pytest + plugins (pytest-cov, pytest-asyncio, pytest-timeout)
- Linting (flake8 + plugins, black, isort)
- Type checking (mypy)
- Security (bandit, safety)
- Documentation (sphinx)

---

## Local Development

### Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run Tests Locally

```bash
# Run all tests with coverage
pytest --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_api_flows.py -v

# Run with markers
pytest -m "not slow" -v
```

### Run Linting

```bash
# Check code formatting
black --check .

# Auto-format code
black .

# Check import sorting
isort --check-only .

# Fix import sorting
isort .

# Run flake8
flake8 .

# Run security scan
bandit -r . -ll
```

### Run Type Checking

```bash
mypy .
```

---

## CI/CD Best Practices

### 1. Test Before Push

Run tests locally before pushing:
```bash
pytest && flake8 . && black --check .
```

### 2. Pre-commit Hooks (Recommended)

Install pre-commit hooks:
```bash
pip install pre-commit
pre-commit install
```

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.1.1
    hooks:
      - id: flake8
```

### 3. Branch Protection Rules

Recommended settings for `main` branch:
- ✅ Require pull request reviews (1 approver)
- ✅ Require status checks to pass
  - `lint`
  - `test (3.11)`
  - `test (3.12)`
  - `integration-test`
- ✅ Require branches to be up to date
- ✅ Require conversation resolution
- ✅ Do not allow bypassing

### 4. Secrets Management

**Required Secrets** (GitHub Settings > Secrets):
- `CODECOV_TOKEN` - Codecov integration (optional)
- `GITHUB_TOKEN` - Automatically provided

**Optional Secrets**:
- `SLACK_WEBHOOK` - Slack notifications
- `DISCORD_WEBHOOK` - Discord notifications

---

## Monitoring & Alerts

### GitHub Actions Notifications

Configure notifications:
1. Go to GitHub Settings > Notifications
2. Enable "Actions" workflow notifications
3. Choose notification method (email, web, mobile)

### Status Badges

Add to README.md:

```markdown
![Tests](https://github.com/uzaktantakip000-create/piyasa_chat_bot/workflows/Tests%20%26%20Code%20Quality/badge.svg)
![Docker Build](https://github.com/uzaktantakip000-create/piyasa_chat_bot/workflows/Docker%20Build%20%26%20Push/badge.svg)
![CodeQL](https://github.com/uzaktantakip000-create/piyasa_chat_bot/workflows/CodeQL%20Security%20Scanning/badge.svg)
[![codecov](https://codecov.io/gh/uzaktantakip000-create/piyasa_chat_bot/branch/main/graph/badge.svg)](https://codecov.io/gh/uzaktantakip000-create/piyasa_chat_bot)
```

### Coverage Reports

- **Codecov**: Upload coverage.xml (automated in workflow)
- **Local HTML**: `htmlcov/index.html` after running pytest

---

## Troubleshooting

### Common Issues

**1. Tests fail in CI but pass locally**
- Check Python version match (use 3.11 or 3.12)
- Verify environment variables
- Check Redis service availability

**2. Docker build fails**
- Verify Dockerfile.api syntax
- Check .dockerignore patterns
- Ensure all dependencies in requirements.txt

**3. Linting errors**
- Run `black .` and `isort .` to auto-fix
- Check .flake8 config for ignored rules

**4. Coverage too low**
- Add tests for uncovered code
- Check .coveragerc omit patterns
- View htmlcov/index.html for details

### Debug Workflows

Enable debug logging:
1. Go to repository Settings > Secrets
2. Add `ACTIONS_STEP_DEBUG` = `true`
3. Add `ACTIONS_RUNNER_DEBUG` = `true`

---

## Roadmap

### Planned Improvements

- [ ] Automated deployment to staging/production
- [ ] Performance benchmarking in CI
- [ ] Visual regression testing
- [ ] Automatic changelog generation
- [ ] Slack/Discord integration for notifications
- [ ] Dependabot configuration
- [ ] Release automation

---

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [CodeQL Action](https://github.com/github/codeql-action)
- [Codecov Action](https://github.com/codecov/codecov-action)
- [Pytest Documentation](https://docs.pytest.org/)
- [Black Documentation](https://black.readthedocs.io/)
- [Flake8 Documentation](https://flake8.pycqa.org/)

---

*Last Updated: 2025-11-03 - Session 34*
*CI/CD Pipeline: PRODUCTION READY*
