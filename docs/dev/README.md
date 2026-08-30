# Developer Notes

## Primary Checks

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pre-commit run --all-files
uv run python -m dnadesign_data.devtools.docs_check
uv run python -m dnadesign_data.devtools.publication_check
uv run python -m dnadesign_data.devtools.public_tree_check
uv lock --check
uv build
uv run python -m dnadesign_data.devtools.package_artifact_check
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
- exact wheel/sdist inventory and package privacy inspection.

## Public release verification

The latest advertised data release is `v0.1.0a4`. Current `main` contains
post-release validation hardening and is not itself a tagged release. This page
does not reserve the next version. When a release is authorized, choose its
version explicitly and require the candidate tag to match the project version
at a clean `HEAD` with exactly one rooted public history. An initial public
push may have an all-zero GitHub `before` SHA; the publication check treats
that event as a diff from Git's empty tree.

Publish the prepared root before creating repository-revision receipts. After
the canonical remote advertises that exact root, create the receipts and pool
inventories in a second commit, regenerate `PUBLIC_DATA_INVENTORY.json`, and
rerun every gate. Tag only after that receipt-bootstrap commit is complete.

The final release verification clone must be made from the published root with
`git clone --no-local --no-tags --single-branch` into a new directory. Fetch
only the candidate release tag after verifying the canonical public branch. This
no-local/no-extra-tags clone is required because a copied `.git` directory can
retain unreachable objects from superseded private history even when the
visible branch has one root. Run the full checks and
`dnadesign-data-public-tree --require-tag <release-tag>` in that clone.
