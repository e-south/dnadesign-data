# Developer Notes

## Primary Checks

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pre-commit run --all-files
uv run python -m dnadesign_data.devtools.docs_check
uv lock --check
uv build
git diff --check
```

## Architecture Guardrails

The test suite includes repository information-architecture checks:

- required top-level routing docs exist;
- `AGENTS.md` stays short;
- tracked Python lives under `src/` or `tests/`;
- source modules stay below the monolith threshold.

These checks are intentionally conservative. If a legitimate exception appears,
document the exception in `ARCHITECTURE.md` before changing the test.

## CLI Smoke Paths

```bash
uv run dnadesign-data-ecocyc-go --help
uv run dnadesign-data-biocyc-smarttables --help
uv run dnadesign-data-sources list --kind all --indent 0
uv run dnadesign-data-sources schema --indent 0
uv run dnadesign-data-sources check --require-source regulondb_13_tf_riset --summary-only --indent 0
```

Authenticated BioCyc runs require explicit local credentials. See
`../../SECURITY.md` and `../functional-annotations.md` for the private-file and
Keychain handoff flow.

## CI Contract

The GitHub Actions workflow mirrors the local checks:

- cached `uv` setup through `astral-sh/setup-uv`;
- `uv.lock` freshness checks;
- documentation routing checks;
- Ruff format and lint;
- all pre-commit hooks;
- full pytest suite on Python 3.8 and 3.12;
- CLI smoke for public data adapters and the source catalog list/schema/check
  surface;
- package build smoke on Python 3.12.
