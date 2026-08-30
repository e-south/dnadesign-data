---
id: motif-source-providers
intent: Describe implemented provider capabilities and explicit extension criteria.
audience: package-user
load: on-demand
navigation:
  parent: README.md
  contracts: contracts.md
  methods_provenance: methods-provenance.md
---

# Motif Source Providers

## Implemented

| Provider ID | Input | Output | Important boundary |
| --- | --- | --- | --- |
| `meme_probability_matrix_v1` | One explicitly named MEME probability matrix | `motif-model/v2` | Zero values require the separately versioned 0.1 background mixture. |
| `jaspar_count_matrix_v1` | One explicitly named JASPAR count matrix | `motif-model/v2` | Uses the per-position background-weighted `sqrt(N_i)` count prior. |
| `regulondb_tf_riset_sites_v1` | Release-pinned RegulonDB TF-RISet table | `dnadesign-data.binding-site-set/v1` | Does not infer alignment, site window, or PWM. |

Both providers are local and deterministic. They perform no network discovery.
The Python facade exposes the same bounded capability catalog as
`dnadesign-data-motifs providers`.

## Current Source Descriptors

- `jaspar_2026_core_meme` describes selected JASPAR CORE 2026 MEME records
  admitted for canonical export. The tracked panel includes human CEBPB
  (`MA0466.4`), RELA (`MA0107.1`), FOS::JUN (`MA0099.4`), GATA1
  (`MA0035.5`), TAL1::TCF3 (`MA0091.2`), SOX2 (`MA0143.5`), and REST
  (`MA0138.1`), plus *Arabidopsis thaliana* HY5 (`MA0551.2`) and PIF3
  (`MA0560.2`). Their exact source bytes are tracked under the database shelf,
  and their canonical models use the explicit probability mixture documented
  in each export manifest. JASPAR identifies its data as CC BY 4.0;
  attribution and record links remain attached through the source descriptor
  and bytes. These clean-room models are deterministic and have accepted owner
  receipts bound to the newly advertised clean-room root.
- `jaspar_2026_core_counts` describes 16 exact JASPAR CORE 2026 count records
  retrieved through the official matrix API. Twelve human records form a
  coherent higher-order candidate set. Two *Arabidopsis thaliana* and two
  *Drosophila melanogaster* records provide fresh within-context pair
  candidates. Their record ledger preserves source IDs, taxa, assay labels,
  widths, mean observed counts, rights posture, retrieval URLs, source digests,
  and development-exposure state. Converted artifacts are deterministic and
  carry accepted receipts bound to the publicly advertised clean-room root.
- `hocomoco_14_core_meme` describes selected HOCOMOCO 14 CORE probability
  matrices. The first bounded set contains MAX (`MAX.H14CORE.0.PS.A`), MYCN
  (`MYCN.H14CORE.0.PS.A`), and SP1 (`SP1.H14CORE.0.P.B`). HOCOMOCO publishes
  CORE matrices directly in MEME format, so these records reuse
  `meme_probability_matrix_v1`; there is no HOCOMOCO-specific provider. The
  official download page distributes the collection under WTFPL and explicitly
  permits treating it as CC-BY. Exact local digests, record URLs, retrieval
  dates, source species, and the single terminal-blank-line normalization are
  recorded in `sources/databases/hocomoco/14/CORE/records.tsv`. The canonical
  models are deterministic derivatives: the shared MEME conversion applies
  the manifest-declared `probability_matrix_prior_mixture_v1` with weight 0.1,
  so their probabilities are not literal copies of the source rows. These
  clean-room models likewise carry accepted receipts bound to the publicly
  advertised clean-room root.
- `omalley_2021_ecoli_meme` describes the O'Malley *et al.* supplementary
  *E. coli* MEME reports. Its redistribution status is `private_storage`:
  neither source reports nor derived model bytes belong in this public tree.
  A private model may receive an accepted receipt only when one verified
  `dnadesign.storage-object/v1` store binds the exact source and model members
  to an advertised `dnadesign-data` converter revision.
- `regulondb_13_tf_riset_sites` describes the release-13 TF-RISet site table.
  Its derived records remain `private_storage` under the current source terms.

## Other Common Shapes

- JASPAR-style count matrices now have one explicit data-owner conversion.
  The count route and the MEME probability route remain separate because a
  count prior and a probability mixture do not carry the same semantics.
- Choudhary *et al.* BaeR evidence already has a named private hydration
  adapter. It should feed a typed site set after authorized hydration, not a
  hidden fallback model.
- A second biological or taxonomic context may add another named descriptor
  and provider only when a real study task requires it.

## Deliberately Deferred Sources

- CIS-BP 3.10 is a valuable broad inventory, but its records aggregate
  heterogeneous upstream rights and mix direct and inferred TF associations.
  It needs record-level provenance and redistribution review before admission.
- RegPrecise 3.2 and CollecTF are site-evidence sources, not unambiguous
  release-pinned probability-model feeds. They require a typed site-set route,
  rights resolution, and a study-owned model-construction policy.
- RegulonDB remains the implemented private site-set example. Its rows must not
  be silently converted into a public PWM.

## Extension Gate

Add a provider only when all of these are known:

1. source identity and release;
2. stable record-selection rule;
3. orientation and deduplication semantics;
4. output schema and deterministic byte contract;
5. missingness and invalid-input behavior;
6. redistribution status;
7. one real-data replay and negative-path tests.

Do not add dynamic entry points or a plugin registry for a source that has not
crossed this gate.
