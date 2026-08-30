# Quality Score Scaffold

Use this scaffold for review, not as a vanity metric. A change is ready when the
relevant checks pass and residual risks are explicit.

## Structural Quality

- Python code is under `src/dnadesign_data/`.
- Tests are under `tests/`.
- Data folders contain artifacts, not active helper modules.
- Top-level `AGENTS.md` routes to docs instead of becoming a monolith.
- Top-level `README.md` stays lightweight and routes detailed source catalogs
  into `docs/`.
- Source modules stay focused enough to review.

## Data Quality

- Source descriptors have stable IDs and releases.
- Generated artifacts include manifests.
- Manifests record row counts and source provenance.
- Empty outputs are either hard failures or explicitly allowed by config.
- Downstream semantics do not leak into generic source-discovery modules.

## Security Quality

- No committed secrets.
- No committed account identities.
- Credential handoff files are ignored and permission-checked.
- Authenticated workflows avoid printing or manifesting credentials.

## Verification Baseline

Run before handoff:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pre-commit run --all-files
git diff --check
```

For CLI changes, also run the relevant `--help` path and at least one dry or
fixture-backed user path.
