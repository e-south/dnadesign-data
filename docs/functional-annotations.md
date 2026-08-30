# Functional Annotations

Functional annotation workflows connect RegulonDB regulator identities to
source-backed biological terms. The release-pinned GO/EcoCyc bulk route is the
default reproducible source. The authenticated BioCyc SmartTable route is a
service-backed companion used when EcoCyc's current SmartTable transforms are
the desired provenance path.

## Release-Pinned EcoCyc/GO

Build the local GO annotation artifacts with:

```bash
uv run dnadesign-data-ecocyc-go --root . run --download-method curl
```

Outputs are written under `generated/functional_annotations/gene_ontology/<GO release>/processed/`:

- `go_terms.tsv`
- `ecocyc_go_gene_product_annotations.tsv`
- `regulator_go_annotations.tsv`
- `regulator_go_coverage.tsv`
- `manifest.json`

The manifest records source URLs, release IDs, SHA-256 hashes, row counts, and
the regulator identity source used for the join.

## Authenticated BioCyc SmartTables

BioCyc SmartTables provide a credentialed service route for GO transforms:
`go-mf`, `go-bp`, and `go-cc`. The adapter builds a Genes SmartTable from the
RegulonDB regulator-gene identity source, adds a `common-name` property column,
adds the GO transform columns, and retrieves the table with the runtime-reported
EcoCyc KB version.

Runtime credentials are never stored in manifests or source code. Use
`--username`, `BIOCYC_USERNAME`, a private password file, an interactive prompt,
or macOS Keychain. The private-file and Keychain handoff is documented in
[Security](../SECURITY.md#biocyc-credential-handoff).

The processed table uses `Common-Name` for the regulator gene-symbol join.
SmartTable GO cells are treated as GO-ID lists; GO names and namespaces are
resolved from the release-pinned GO ontology so `go_name` does not depend on
ambiguous SmartTable cell formatting. Raw create responses are sanitized before
being written because BioCyc may return session material.

Run the adapter with:

```bash
export BIOCYC_USERNAME="<your BioCyc account email>"
uv run dnadesign-data-biocyc-smarttables --root . --prompt-password --json-errors
```

SmartTable outputs are written under
`generated/functional_annotations/biocyc/<reported KB version>/smarttables/regulator_go_terms/`.

The current materialized KB 29.6 outputs are exposed through the source catalog:

- `biocyc_29_6_smarttable_regulator_go_terms`
- `biocyc_29_6_smarttable_regulator_go_coverage`

Downstream tools should resolve these source IDs through
`dnadesign_data.catalog.sources.resolve_source_record` or
`dnadesign-data-sources resolve`. They should not infer the generated path.

The output contract is:

- `processed/regulator_go_terms.tsv`: one row per regulator, gene symbol, GO
  aspect, and GO ID.
- `processed/regulator_go_coverage.tsv`: one row per RegulonDB regulator
  identity, with matched/unmatched status.
- `processed/manifest.json`: KB version, source descriptors, SHA-256 hashes,
  row counts, schema version, transform IDs, and credential boundary.
- `raw/create_response.json`: sanitized SmartTable creation response with
  session material redacted.

## Claim Boundary

These artifacts provide curated regulator-to-term associations. They do not
decide study semantics, active-learning candidates, or latent-space
interpretation. Downstream projects should treat them as provenance-backed
annotation sidecars.
