# Package APIs

The Python package is a thin interface over source data. It should identify
what data exists, where it lives, and which parser route downstream tools should
use. It should not embed study-specific interpretation.

## Source Discovery

| Module | Purpose |
| --- | --- |
| `dnadesign_data.catalog` | Public descriptor facade for source discovery. |
| `dnadesign_data.catalog.sources` | JSON-ready catalog payloads, source resolution, and availability checks. |
| `dnadesign_data.catalog.regulatory_parts` | Promoter source files and TF/promoter association sources. |
| `dnadesign_data.catalog.functional_annotations` | GO/EcoCyc/BioCyc annotation sources and regulator identity sources. |

Root-level compatibility modules are not provided. Downstream callers should use
the catalog package or CLI so stale imports fail fast during integration.

## Source Catalog CLI

| Entrypoint | Purpose |
| --- | --- |
| `dnadesign-data-sources list` | Emit available or known source descriptors as JSON. |
| `dnadesign-data-sources resolve` | Resolve one `source_id` and fail if its backing file is missing. |
| `dnadesign-data-sources check` | Check required source IDs and exit nonzero when contracts fail. |
| `dnadesign-data-sources schema` | Emit the JSON field and exit-code contract without reading source files. |

The CLI is intentionally machine-first: JSON is the default and stable output
contract, `--format json` is explicit for agent harnesses, `--indent 0` emits
compact output, and `--json-errors` emits structured errors to `stderr`.
Readiness checks distinguish live service descriptors from local file sources;
`local_file_available_count` is the field to gate workflows that need materialized
data.

Examples:

```bash
uv run dnadesign-data-sources list --kind all --format json
uv run dnadesign-data-sources schema --format json --indent 0
uv run dnadesign-data-sources resolve regulondb_13_tf_riset --format json --indent 0
uv run dnadesign-data-sources resolve biocyc_29_6_smarttable_regulator_go_terms --format json --indent 0
uv run dnadesign-data-sources check --require-source regulondb_13_tf_riset --summary-only --json-errors
```

## Functional Adapters

| Entrypoint | Purpose |
| --- | --- |
| `dnadesign-data-ecocyc-go` | Download and build release-pinned EcoCyc/GO regulator annotation artifacts. |
| `dnadesign-data-biocyc-smarttables` | Retrieve authenticated BioCyc SmartTable regulator GO annotations. |

See [Functional annotations](functional-annotations.md) for the output
contracts, provenance files, and credential boundary.

## Motif Source Exports

| Entrypoint | Purpose |
| --- | --- |
| `dnadesign-data-motifs providers` | List implemented source shapes and output capabilities. |
| `dnadesign-data-motifs export-meme` | Export one explicit MEME matrix as `motif-model/v1`. |
| `dnadesign-data-motifs export-regulondb-sites` | Preserve one regulator's TF-RISet evidence as `binding-site-set/v1`. |
| `dnadesign-data-motifs receipt` | Bind a model and catalog source to byte-verified blobs at a publicly advertised owner Git revision; Storage fails closed. |

See [Motif source exports](motif-sources/README.md) for the contract boundary
and provider-specific semantics. The adapter set is intentionally bounded;
source discovery is not a runtime Motif Balance responsibility.

## Literature Adapters

| Entrypoint | Purpose |
| --- | --- |
| `dnadesign-data-choudhary-baer` | Hydrate Choudhary et al. BaeR ChIP-exo binding-site artifacts. |
| `dnadesign-data-bie` | Run Bie et al. transcriptomics helper paths. |

Named literature adapters belong under `src/dnadesign_data/literature/` and
should write reproducible source-local outputs with provenance.

## Development Rule

Add a descriptor or adapter here before downstream projects depend on a new raw
folder convention. That keeps `dnadesign` consumers coupled to a public package
contract instead of a private path guess.
