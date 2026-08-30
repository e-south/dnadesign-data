[![CI](https://github.com/e-south/dnadesign-data/actions/workflows/ci.yml/badge.svg)](https://github.com/e-south/dnadesign-data/actions/workflows/ci.yml)
[![Python 3.10-3.14](https://img.shields.io/badge/python-3.10--3.14-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/package_manager-uv-6f42c1.svg)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/linting-ruff-46a2f1.svg)](https://docs.astral.sh/ruff/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen.svg)](https://pre-commit.com/)

![dnadesign-data wordmark](assets/dnadesign-data-wordmark.svg)

`dnadesign-data` is the source-data companion for
[`dnadesign`](https://github.com/e-south/dnadesign). This clean-room public
tree contains a closed, checksummed set of JASPAR and HOCOMOCO motif matrices,
their deterministic motif-model exports, and the small adapters used to audit
and reproduce them.

The wheel contains the catalog and conversion code, not the source datasets.
Use an explicit repository checkout or data mirror when resolving source
records.

The owner handoff is narrow: `dnadesign-data` preserves source identity, rights
posture, deterministic conversion, and receipts; Motif Balance owns scoring and
design from the resulting `motif-model/v2`; research studies own task selection
and interpretation. Start with [Motif source exports](docs/motif-sources/README.md)
for the supported source-to-model routes.

The repository intentionally contains no RegulonDB, EcoCyc, O'Malley, or other
literature-source payloads. Code for explicitly supplied local inputs remains
available for authorized workflows. See [Third-party data](THIRD_PARTY_DATA.md)
for the data-rights boundary and [PUBLIC_DATA_INVENTORY.json](PUBLIC_DATA_INVENTORY.json)
for the closed byte inventory.

---

## Documentation

- [Docs index](docs/README.md): choose the right route for data catalogs,
  adapter workflows, package APIs, credentials, CI, and agent work.
- [Data sources](docs/data-sources/README.md): retained public sources and the
  boundary for externally supplied local data.
- [Motif source exports](docs/motif-sources/README.md): deterministic model and
  binding-site-set handoffs for Motif Balance.
- [Package APIs](docs/package-apis.md): public catalog modules and source CLI
  for downstream tools.
- [Functional annotations](docs/functional-annotations.md): EcoCyc/GO artifacts,
  BioCyc SmartTables, credential handoff, and provenance outputs.
- [Architecture](ARCHITECTURE.md), [Design](DESIGN.md), [Security](SECURITY.md),
  [Quality score](QUALITY_SCORE.md): repository contracts and review gates.
