# Contributing

Thank you for your interest in this project. This repository is public. Please do not open pull requests that include secrets, credentials, or personal data.

## License

This project is licensed under [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](LICENSE).

- You may contribute non-commercial improvements aligned with the license.
- Commercial use or commercial pull requests require prior coordination with the maintainers at info@tmhsdigital.com.

## Development setup

Requirements: Windows, Python 3.10 or newer (3.11 recommended; see `.python-version`).

```bash
# Git Bash / WSL
make install

# Windows cmd
tasks.bat install
```

`install` creates `.venv`, installs runtime packages from `requirements-lock.txt` when present (otherwise `requirements.txt`), then installs the package in editable mode with dev and build extras.

End users installing the application should continue to use `requirements.txt` as documented in the README. Maintainers and CI use `requirements-lock.txt` for reproducible installs.

## Running checks

```bash
make check          # lint, typecheck, unit tests
tasks.bat check     # same on cmd.exe

make test
make lint
make typecheck
make coverage
make smoke          # scripts/smoke_check.py (not pytest)
```

Legacy entry point: `python run_tests.py` (wraps pytest). Coverage: `python run_tests.py --coverage`.

## Regenerating the lock file

On Python 3.11:

```bash
make lock
# or
tasks.bat lock
# or
python tools/refresh_lock.py
```

Commit the updated `requirements-lock.txt` when runtime dependencies change.

## Pre-commit (optional)

Not installed automatically.

```bash
pip install pre-commit   # or use make install
pre-commit install
pre-commit run --all-files
```

Hooks run ruff on paths outside `autoclicker/`, ruff-format (excluding `autoclicker/`), standard file hygiene checks, and mypy on `autoclicker/` using `pyproject.toml`. Production lint cleanup is deferred to the audit pass; temporary ignores may apply under `autoclicker/`.

## Commit messages

Use one of these prefixes:

- `chore:`
- `docs:`
- `ci:`
- `test:`
- `build:`

## Pull requests

1. Fork and branch from `main` or `develop`.
2. Run `make check` or `tasks.bat check` before opening the PR.
3. Update `CHANGELOG.md` under `[Unreleased]` for user-visible changes.
4. Do not commit `autoclicker_settings.json`, `.env`, keys, or tokens.

## Releases

Releases are created when a version tag is pushed, not on every merge to `main`.

```bash
git tag v1.1.0
git push origin v1.1.0
```

CI builds the Windows executable and publishes a GitHub release for that tag. Use semantic versioning tags matching `v*.*.*`.

## Security

See [SECURITY.md](SECURITY.md). Report concerns by email; do not file public issues for undisclosed vulnerabilities.
