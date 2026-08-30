## `dnadesign-data` For Agents

This repository is a public, uv-managed data package. It contains data folders
plus a small Python package under `src/dnadesign_data/` for source discovery,
provenance, and reproducible data adapters.

Treat this file as a router. Canonical policy lives in the docs below.

## Start Here

- Architecture map: `ARCHITECTURE.md`
- Engineering invariants: `DESIGN.md`
- Security and credential policy: `SECURITY.md`
- Quality scaffold: `QUALITY_SCORE.md`
- Docs index: `docs/README.md`

## Repo Map

- Python package: `src/dnadesign_data/`
- Tests: `tests/`
- Curated source data: `sources/databases/`, `sources/literature/`
- Generated functional annotations: `generated/functional_annotations/gene_ontology/<release>/`,
  `generated/functional_annotations/biocyc/<kb-version>/`
- CI: `.github/workflows/ci.yml`
- Package config: `pyproject.toml`

## Validation

Use the narrowest check that covers your change, then broaden before handoff:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python -m dnadesign_data.devtools.publication_check
uv run pip-audit --local
git diff --check
```

Discover CLIs from `[project.scripts]` in `pyproject.toml`, or run:

```bash
uv run dnadesign-data-ecocyc-go --help
uv run dnadesign-data-biocyc-smarttables --help
uv run dnadesign-data-sources list --kind all --indent 0
uv run dnadesign-data-sources schema --indent 0
uv run dnadesign-data-sources check --require-source regulondb_13_tf_riset --summary-only --indent 0
```

## Change Boundaries

- Keep importable Python under `src/dnadesign_data/`.
- Keep tests under `tests/`.
- Do not add ad-hoc scripts inside data-source folders.
- Do not commit secrets, account identities, local credential handoff files, or
  machine-local paths.
- Preserve raw source files unless the user explicitly requests a data
  migration.
- Require an explicit redistribution status before adding literature payloads;
  keep review-blocked or link-only source bytes in private storage.
- Prefer source descriptors, manifests, and stable parser hints over hidden
  downstream assumptions.

## Generated Artifacts

Treat these as generated unless a task explicitly asks to refresh them:

- `generated/functional_annotations/gene_ontology/<release>/annotations/`
- `generated/functional_annotations/gene_ontology/<release>/ontology/`
- `generated/functional_annotations/gene_ontology/<release>/processed/`
- `generated/functional_annotations/biocyc/<kb-version>/smarttables/`
- `**/__pycache__/`, `.pytest_cache/`, `.ruff_cache/`

Do not hand-edit generated outputs. Fix package code/config and regenerate.
