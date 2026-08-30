---
id: motif-source-methods-provenance
intent: Record primary lineage for source shapes and matrix-conversion policies.
audience: package-user
load: on-demand
navigation:
  parent: README.md
  contracts: contracts.md
  providers: providers.md
---

# Motif Source Methods Provenance

This record explains why each conversion exists. It is not a literature review
and does not make one database's scores interchangeable with another's.

## Source lineage

- [JASPAR 2026](https://doi.org/10.1093/nar/gkaf1209) describes the 11th
  database release. The [official JASPAR site](https://jaspar2026.elixir.no/)
  identifies CORE as curated, non-redundant transcription-factor binding
  profiles, exposes position-frequency matrices, and states the CC BY 4.0
  license. The count records in this repository come from the official
  release-specific matrix API, not from rounded historical outputs.
- [HOCOMOCO v14](https://doi.org/10.1093/nar/gkad1077) describes the curated
  human and mouse model collection. The
  [official download surface](https://hocomoco14.autosome.org/downloads_v14)
  publishes PCM, PFM, PWM, JASPAR, and MEME forms separately. The
  [official help](https://hocomoco14.autosome.org/help) states that its PCM to
  PWM scheme follows MACRO-APE and that uniform background was used for
  downloadable score thresholds. Existing admitted HOCOMOCO MEME files are
  therefore treated as supplied probability matrices; counts are not inferred
  from them.
- The [MEME motif-format contract](https://meme-suite.org/meme/doc/meme-format.html)
  defines letter-probability rows and `nsites` separately. The
  [matrix2meme documentation](https://meme-suite.org/meme/doc/matrix2meme.html)
  describes background-weighted pseudocounts for count or frequency inputs.
  These sources support preserving the distinction between observed counts and
  already-derived probabilities.

## Count prior lineage

The [Biopython motif documentation](https://biopython.org/docs/latest/Tutorial/chapter_motifs.html)
records the JASPAR/TFBS compatibility convention in which the prior mass is
`sqrt(N)` and each base receives that mass weighted by its background
probability. This implementation applies that rule independently at each
position using its observed row total `N_i`. It serializes `N_i`, `sqrt(N_i)`,
and `N_i + sqrt(N_i)` for exact replay. This is recorded as
`count_matrix_sqrt_n_background_prior_v1` under `motif-conversion/v2`.

The probability route does not reconstruct counts from `nsites`. Its explicit
0.1 background mixture remains `probability_matrix_prior_mixture_v1`. That
rule is a deterministic regularization choice for already-derived probability
rows, not an assertion that 0.1 observations were added to a count matrix.

## Numeric defect record

Repeated binary64 division can alternate between two adjacent representations
of the same unit-sum row. HOCOMOCO's higher-precision probability rows exposed
this failure mode during expansion. The canonicalizer now detects a repeated
state, selects one canonical cycle endpoint, and assigns the residual once to a
deterministic base. Entering through either adjacent binary64 representation
therefore produces the same bytes.

## Qualification boundary

An exported model is `conversion_verified_pending_receipt` until an advertised
owner revision binds the exact source and model blobs. It becomes
`accepted_owner_receipt` only through receipt verification. Development
exposure is derived independently from the owner-maintained exposure ledger:
an accepted model or task can still be ineligible because it informed prior
dogfood choices. Pool requests cannot assert or erase that history. Formal
qualification consumes only ledger blobs reachable from the fixed public
integration or release anchors, unions their exclusions, and requires each
ledger update to retain its parent's model and task entries.

Both the historical v1 and current v2 projections of the 12-model multi-source
development panel are explicitly exposed.
The new count-derived request now reports `qualification_ready`: its receipts
bind source and model bytes at the advertised clean-room revision. This remains
only a data-authority state; prospective study chronology is frozen by Research
Studies. RegulonDB remains a private site-set route, and review-blocked O'Malley
bytes are not used to fill that gap.

Database payload publication is independently gated by release-local rights and
attribution records. Generated motif bundles must resolve to a redistributable
catalog descriptor and a redistributable database-rights record before public
commit.
