# Third-party data

The MIT license in [LICENSE](LICENSE) applies to the project code and original
documentation. It does not relicense third-party source data.

This clean-room public tree contains only the source matrices needed to replay
the published JASPAR 2026 and HOCOMOCO 14 motif-model bundles. Each retained
database release carries its own rights metadata and attribution:

| Data | Retained scope | Rights and attribution |
| --- | --- | --- |
| JASPAR 2026 CORE | 16 count matrices and 9 probability matrices used by the retained model bundles | [`sources/databases/jaspar/2026/rights.json`](sources/databases/jaspar/2026/rights.json) |
| HOCOMOCO 14 CORE | 3 probability matrices used by the retained model bundles | [`sources/databases/hocomoco/14/rights.json`](sources/databases/hocomoco/14/rights.json) |

The complete retained-data inventory, including byte sizes and SHA-256
digests, is [PUBLIC_DATA_INVENTORY.json](PUBLIC_DATA_INVENTORY.json). The
publication gate rejects undeclared data, digest drift, absent rights metadata,
and any source whose posture is not explicitly `redistributable`.

RegulonDB, EcoCyc, O'Malley and all other literature-source payloads are not
part of this public tree. Some package adapters and descriptors remain so that
authorized callers can use separately supplied local data. Their presence is
not a grant to redistribute those external sources.

The motif artifacts are deterministic project-generated representations of
the named source matrices. Repository-revision receipts were intentionally
absent from the clean-room initial commit and were issued only after the new
canonical remote advertised the exact source and model commit. Every retained
bundle now has an accepted owner receipt bound to that advertised revision.
