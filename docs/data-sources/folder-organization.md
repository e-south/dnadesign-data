# Folder Organization

The repository uses semantic shelves:

| Shelf | Role |
| --- | --- |
| `sources/databases/regulondb/<release>/` | Release-pinned RegulonDB exports and historical comparison data. |
| `sources/databases/ecocyc/<release>/` | Release-pinned EcoCyc exports and SmartTables. |
| `sources/databases/jaspar/<release>/` | Rights-reviewed, release-pinned JASPAR records. |
| `sources/literature/<citation_slug>/` | Citation-scoped primary-literature artifacts. |
| `generated/functional_annotations/gene_ontology/<release>/` | GO/EcoCyc inputs plus reproducible processed outputs. |
| `generated/functional_annotations/biocyc/<kb-version>/` | Authenticated BioCyc SmartTable outputs when materialized. |
| `generated/motif_models/<source-release>/<motif>/` | Canonical source-bound motif export bundles. |

New code should use `dnadesign_data` source descriptors or CLI outputs instead
of hard-coding these folders.

## Ontology

The semantic split is:

```text
sources/
  databases/
    regulondb/<release>/
    ecocyc/<release>/
    jaspar/<release>/
  literature/
    <citation_slug>/
generated/
  functional_annotations/
    gene_ontology/<release>/
    biocyc/<kb_version>/
  motif_models/<source-release>/<motif>/
```

Rules:

- `sources/` holds externally obtained or manually curated source artifacts.
- `generated/` holds artifacts reproducible from package CLIs or adapters.
- Importable Python stays under `src/dnadesign_data/`.
- Source shelves do not contain active scripts.
- Future path changes require descriptor updates, docs updates, and downstream
  contract tests in the same migration.

Do not migrate paths by adding silent fallback search logic. A layout migration
should have one explicit active layout version and fail fast when required
artifacts are missing.
