# Agent notes

## Development setup

```bash
mise install
mise run setup
```

`mise run setup` creates `.venv`, installs Python test/lint deps, and installs **hk** git hooks (`pre-commit`: ruff + jactionlint; `pre-push`: pytest when Python-related files are pushed).

Run checks manually: `hk check`, `hk check --all`, or `uv run --no-project pytest` / `ruff`.
