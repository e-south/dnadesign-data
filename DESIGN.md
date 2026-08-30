# Design Invariants

## Public Package Boundary

`dnadesign-data` is public. Code must be safe to publish:

- no hard-coded user identities;
- no secrets or credential material;
- no machine-local absolute paths;
- no import-time network calls.

## Source Descriptor Pattern

Use descriptor dataclasses for source discovery. A descriptor should include:

- stable `source_id`;
- source name and release;
- repository-relative path or service base URL;
- table/role/stratum semantics;
- file format or response format;
- parser hint for downstream adapters.

Motif-source descriptors also expose the retrieval route, rights route, and
retrieval date when known. The export manifest binds the selected source bytes
and release; an accepted receipt additionally binds those bytes and the model
to one advertised owner revision.

Discovery can report which sources exist locally, but it should not silently
reinterpret missing sources.

Literature publication is independent from parser availability. A source
package records `redistribution_status`; review-blocked or link-only payloads
remain in private storage even when a parser can consume them locally.

## Adapter Pattern

Adapters should be explicit, reproducible, and fail fast:

- accept a repository root;
- validate required inputs before writing outputs;
- preserve raw responses or source hashes when practical;
- write processed tables with stable columns;
- write a manifest with source routes, row counts, schema version, and hashes;
- avoid mutating unrelated data folders.

For motif sources, distinguish an observed binding-site set from a probability
model. Orientation normalization may be source-owned when it is lossless and
declared. Alignment, trimming, site windows, background choice, and prior
mixtures are explicit versioned conversions; none may be inferred from a
historical workspace configuration.

## File Organization

- Importable code belongs under `src/dnadesign_data/`.
- Tests belong under `tests/`.
- Data folders are data-only unless a file is archival and ignored.
- Prefer focused modules named by responsibility over broad utility modules.
- Split modules before they accumulate unrelated concerns such as credentials,
  parsing, artifact writing, and CLI orchestration.

## Failure Policy

Fail fast on:

- missing required source files;
- missing required columns;
- empty outputs unless an explicit `allow_empty_*` flag exists;
- malformed credentials or unsafe password-file permissions;
- unsupported source formats or parser hints.

Do not add silent fallbacks. If degraded behavior is needed, make it an
operator-visible option and record it in the manifest.
