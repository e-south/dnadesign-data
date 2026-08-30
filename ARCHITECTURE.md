# Architecture

`dnadesign-data` is a public data repository with a small helper package. This
clean-room tree publishes only a closed JASPAR/HOCOMOCO motif source set. The
main architectural boundary is simple:

- data folders store source and generated artifacts;
- `src/dnadesign_data/` stores importable Python;
- downstream projects own study-specific interpretation.

## Layers

### Source Data

Source shelves under `sources/` hold explicitly redistributable external
artifacts. Generated shelves under `generated/` hold reproducible package
outputs. Code may describe separately supplied local sources without including
their bytes in the public tree.

The active folder ontology separates external sources from generated artifacts:

- `sources/databases/<provider>/<release>/`
- `generated/motif_models/<source-release>/<motif>/`

Any future physical migration must update public source descriptors,
documentation, and downstream contract tests in the same change. Source shelves
should not contain active Python modules.

### Source Discovery

Public discovery modules expose stable descriptors for downstream tooling:

- `dnadesign_data.catalog`
- `dnadesign_data.catalog.sources`
- `dnadesign_data.catalog.regulatory_parts`
- `dnadesign_data.catalog.functional_annotations`
- `dnadesign_data.motifs`

These modules describe source IDs, releases, paths, table roles, formats, and
parser hints. They do not parse biological records into study-specific models.
Legacy root-level discovery modules are intentionally absent; stale imports
should fail fast rather than silently resolving through compatibility shims.

The `dnadesign-data-sources` CLI is the shell-facing public contract for sibling
repositories. It emits JSON by default, supports `--format json` explicitly,
uses nonzero exits for failed availability checks, and can emit JSON errors with
`--json-errors`. Its `schema` subcommand emits the field and exit-code contract
without inspecting source files.

### Data Adapters

Adapter modules under `src/dnadesign_data/` materialize reproducible local
artifacts from source files or source-backed web services:

- `functional/ecocyc_go.py` handles release-pinned GO/EcoCyc bulk files.
- `functional/biocyc_smarttables.py` handles BioCyc SmartTable retrieval.
- `functional/go_parsers.py` holds GO and SmartTable parsers.
- `functional/biocyc_client.py` holds the authenticated BioCyc client.
- `functional/table_io.py` holds shared table, manifest, and byte-file I/O.
- `literature/*` handles named primary-literature processing.
- `motifs/*` exports named probability-matrix or binding-site source shapes
  through typed, deterministic artifacts and content-bound receipts.

Adapters must write manifests with source routes, release/version identifiers,
hashes where practical, and row counts. Source modules are kept below the
repository monolith threshold so parser, client, I/O, and CLI concerns remain
reviewable.

### Runtime Credential Boundary

Credential resolution lives in `functional/biocyc_credentials.py`. Public code
must not contain account identities or passwords. Credentials are provided by
environment variable, private file, prompt, or OS credential store at runtime.

## Downstream Contract

Downstream repositories should depend on public descriptors and CLI outputs, not
on private implementation details or raw folder heuristics. If a downstream
tool needs a new semantic layer, add a descriptor or adapter contract here before
consuming it there.

Motif-source flow has three owner boundaries: this repository preserves source
identity and deterministic export; a study owns alignment, site-window, and
model-selection policy; Motif Balance owns scoring and design from
`motif-model/v2`. Historical `motif-model/v1` artifacts remain readable but are
not the current handoff. Storage owns artifact placement, not biological
semantics.

## Non-Goals

- No study-specific LatentDNA, OPAL, Infer, Construct, or USR logic.
- No broad ontology interpretation in source-discovery modules.
- No hidden network fetches during import.
- No universal TFBS adapter or dynamic source plugin registry.
- No loose Python scripts in data folders.
