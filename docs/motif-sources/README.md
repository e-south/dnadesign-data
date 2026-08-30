---
id: motif-source-exports
intent: Route users from named TFBS sources to canonical, provenance-bound artifacts.
audience: package-user
load: on-demand
navigation:
  contracts: contracts.md
  providers: providers.md
  methods_provenance: methods-provenance.md
---

# Motif Source Exports

Use this surface when source-attested motif records must become an explicit
input to Motif Balance. `dnadesign-data` owns the source record, selection
provenance, and deterministic export. Motif Balance owns scoring and design
from a canonical `MotifModel`.

This is a bounded adapter set, not a universal adapter framework. A provider is
registered only after its source shape, output schema, rights posture, and
negative paths are proven against real data.

## Choose A Route

| Need | Route |
| --- | --- |
| Understand the source-to-model boundary | [Contracts](contracts.md) |
| See implemented and deferred providers | [Providers](providers.md) |
| Audit conversion lineage and numeric policy | [Methods provenance](methods-provenance.md) |
| List machine-readable capabilities | `uv run dnadesign-data-motifs providers` |
| Export one MEME probability matrix | `uv run dnadesign-data-motifs export-meme --help` |
| Export one JASPAR count matrix | `uv run dnadesign-data-motifs export-jaspar-counts --help` |
| Preserve one RegulonDB regulator site set | `uv run dnadesign-data-motifs export-regulondb-sites --help` |
| Bind an accepted model to a verified owner Git blob | `uv run dnadesign-data-motifs receipt --help` |
| Build an exposure-bound task inventory or qualification candidate | `uv run dnadesign-data-motifs build-pool --help` |

## Minimal Flow

```text
named source + release
  -> explicit provider
  -> motif-model/v2 or binding-site-set/v1
  -> immutable verified data-owner Git artifact and receipt
  -> Motif Balance DesignSpec
```

Current design uses `motif-model/v2`; historical `motif-model/v1` artifacts
remain readable but are not rewritten. A binding-site set requires an explicit,
study-owned alignment or site window policy before it can become a probability
model.

`export-meme` uses the source-declared MEME background by default. Use
`--background 0.25,0.25,0.25,0.25` only when a downstream protocol has
prospectively chosen a uniform target background. The export keeps the source
background as provenance and binds the target background separately; it does
not rewrite or conceal what the source declared.

## Distribution Boundary

The Python wheel provides contracts and deterministic conversion code. Source
and generated motif bytes live in the data repository and are not copied into
the wheel. An off-the-shelf workflow therefore uses an explicit data checkout
or mirror plus a named source descriptor; Motif Balance itself never discovers
or downloads a database.
