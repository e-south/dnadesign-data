# Documentation Index

`dnadesign-data` has two jobs: preserve a closed, rights-reviewed public motif
source set and expose small package surfaces that can also operate on
explicitly supplied local sources without hard-coding paths downstream.

## Choose A Route

| Need | Start here |
| --- | --- |
| Understand the repository boundary | [Architecture](../ARCHITECTURE.md) and [Design](../DESIGN.md) |
| Review retained public data and rights | [Data sources](data-sources/README.md) and [Third-party data](../THIRD_PARTY_DATA.md) |
| Export TFBS sources for Motif Balance | [Motif source exports](motif-sources/README.md) |
| Use RegulonDB or EcoCyc source descriptors | [Package APIs](package-apis.md) |
| Inspect or check source descriptors from a shell | [Package APIs](package-apis.md#source-catalog-cli) |
| Build EcoCyc/GO regulator annotations | [Functional annotations](functional-annotations.md) |
| Use authenticated BioCyc SmartTables | [Functional annotations](functional-annotations.md#authenticated-biocyc-smarttables) and [Security](../SECURITY.md) |
| Run primary-literature adapters | [Package APIs](package-apis.md#literature-adapters) |
| Validate or change the repo | [Developer notes](dev/README.md) |
| Review publication safety and credentials | [Security](../SECURITY.md) |
| Review quality gates | [Quality score](../QUALITY_SCORE.md) |
| Route agent work | [Agent router](../AGENTS.md) |

## Source Data

- [Data sources](data-sources/README.md) catalogs the retained JASPAR and
  HOCOMOCO matrices and explains the local-only source boundary.
- Public source bytes stay under `sources/databases/`; generated motif models
  stay under `generated/motif_models/`.
- Generated outputs should be reproduced through package adapters, not
  hand-edited.

## Package Surfaces

- [Package APIs](package-apis.md) maps public catalog descriptors and CLI
  entrypoints.
- [Functional annotations](functional-annotations.md) covers release-pinned
  EcoCyc/GO processing and authenticated BioCyc SmartTable retrieval.
- [Motif source exports](motif-sources/README.md) separates source evidence,
  model construction, immutable authority, and Motif Balance consumption.
- [Security](../SECURITY.md) defines the credential boundary for public code.

## Maintainer Surfaces

- [Developer notes](dev/README.md) lists local checks, CI shape, CLI smoke
  paths, and architecture guardrails.
- [Architecture](../ARCHITECTURE.md), [Design](../DESIGN.md), and
  [Quality score](../QUALITY_SCORE.md) define the review contracts.

## Documentation Rules

- Keep the root README as a front door.
- Keep source catalogs in `docs/` or source-local provenance files.
- Keep commands and operational detail in workflow-specific docs.
- Prefer links over duplicated inventories.
