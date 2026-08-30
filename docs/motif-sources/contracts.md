---
id: motif-source-contracts
intent: Define the typed artifacts and authority boundaries for TFBS source exports.
audience: package-user
load: on-demand
navigation:
  parent: README.md
  providers: providers.md
  methods_provenance: methods-provenance.md
---

# Motif Source Contracts

## Four Separate Decisions

1. Source acquisition identifies a named database or publication snapshot and
   its release, digest, and redistribution status.
2. Source normalization preserves the selected records without inventing a
   motif model.
3. Model construction declares any orientation, alignment, site window,
   background, and prior policy.
4. Motif Balance consumes the resulting immutable model for scoring and design.

`dnadesign-data` owns the first two decisions and deterministic source-format
conversion. A research study owns scientific choices such as aligning
variable-width sites or selecting a fixed window. Motif Balance does not fetch
databases or infer those policies.

## Export Bundle

Every command writes a new directory containing:

| File | Contract |
| --- | --- |
| `artifact.json` | One canonical model or site set. |
| `manifest.json` | Provider, source, selection, rights, schema, and byte digests. |

Publication is create-only and atomic. The manifest schema is
`dnadesign-data.motif-source-export/v1`. It binds a provider ID to one source
descriptor and revision, the source-file digest, explicit selection rules, the
output schema, and the exact canonical artifact digest.

The source catalog is the discovery surface. For motif sources it reports the
retrieval URL, rights URL, recorded retrieval date, release, local route,
output capability, and redistribution status. There is no second source
registry to reconcile.

## Canonical Model

`motif-model/v2` is the current Motif Balance handoff. It contains the literal
DNA alphabet, positive position probabilities, background probabilities, source
identity, explicit conversion provenance, and binds
`relative_pwm_attainment_v2`. Historical `motif-model/v1` artifacts remain
readable and byte-stable; new projections do not rewrite them.

Probability rows and backgrounds are normalized with `math.fsum` followed by
binary64 division. Published probability rows are then required to have one
stable representation. A rare binary64 normalization cycle is resolved by
assigning the residual to the largest probability (first base on a tie) and,
when needed, moving that field by one representable value toward the exact
unit sum. Source rows remain unchanged in their source file; the converted
rows remain in `artifact.json`.

MEME matrices containing zero probabilities require a positive prior mixture:

```text
p_final = (p_source + prior_weight * background) / (1 + prior_weight)
```

That transformation is recorded as
`probability_matrix_prior_mixture_v1`; it is never applied silently.
This contract admits exactly the declared 0.1 mixture for current probability
exports. It is distinct from count conversion.

By default, the MEME source-declared background is used both for that mixture
and as the model's scoring background. A caller that needs one prospectively
declared study background may pass `background` through the Python API or
`--background A,C,G,T` through `export-meme`. The resulting
`probability_matrix_target_background_v1` conversion binds all three facts
separately:

- the background parsed from the source MEME bytes;
- the explicit target background used for regularization and scoring;
- the `explicit_target_background_v1` selection policy.

This explicit conversion requires a positive `prior_weight`, even when every
source probability is already positive. A zero prior remains valid only for
the legacy no-override path, where it preserves the source matrix and its
historical canonical bytes.

Receipt validation replays the source conversion with the recorded target
background and rejects disagreement with either background. Omitting the
override retains the historical manifest, conversion, artifact, and receipt
bytes; existing receipts require no migration. Supplying an override always
creates a new canonical artifact identity and therefore requires a new export
and receipt rather than reinterpreting an existing artifact. Its mathematical
model digest also changes unless the explicit target equals the source
background.

JASPAR count matrices use `count_matrix_sqrt_n_background_prior_v1`. At each
position `i`, let `N_i` be the observed row total and let `q_b` be the declared
background. The position prior mass is `alpha_i = sqrt(N_i)`, base `b` receives
`alpha_i * q_b`, and the denominator is `N_i + alpha_i`. The Motif Balance
handoff records `source_motif_id`, every `N_i`, every `alpha_i`, and every
denominator under `motif-conversion/v2`; there is no matrix-level
`sequence_count` or `total_prior`. The selection policy independently binds the
declared background
and conversion-contract version, so changing both the model and its background
cannot reinterpret one admitted source. It does not describe the count prior as
one scalar probability mixture. Negative, nonfinite, missing, unequal-width,
overflowing, zero-total,
and trailing source content fail before publication.

## Task-driven pools

A pool request names only exact model bundles and task membership. Qualification
is derived from revalidated receipts. Exposure is derived from the separately
maintained development-exposure ledger and its digest; callers cannot relabel
known models or task combinations. Formal qualification reads the ledger only
from fixed advertised integration or release anchors, records their revisions
and digests, rejects non-append-only ledger history, and requires every admitted
bundle to be byte-identical at one of those anchors. `development` mode
inventories the current local state. `formal` mode source-replays even models
that do not yet have receipts, rejects ledger-exposed inputs, and reports local
preintegration work as `local_untrusted` and `qualification_pending`. Once the
exact bytes are advertised and receipted it may report `qualification_ready`.
It never claims that source qualification alone seals a prospective Research
Studies cohort.

## Binding-Site Set

`dnadesign-data.binding-site-set/v1` preserves selected TFBS evidence when the
source does not already provide one usable probability matrix. The RegulonDB
provider records genomic coordinates, source strands, uppercase-core sequence
semantics, usable-site counts, exclusions, observed widths, and model readiness.

Reverse-strand sequences are reverse-complemented into genomic-forward
orientation so repeated observations of one genomic site can be reconciled.
Unequal widths remain unequal. The adapter does not center, trim, align, pad, or
construct a PWM.

## Authority Receipt

After a canonical model is committed to the owner Git repository, the data
owner can issue `dnadesign-data.motif-export-receipt/v1`. Receipt creation
reloads canonical bundle bytes, re-hashes the catalog-selected source, and
replays the declared conversion from those exact bytes. A self-consistent model
whose scientific fields differ from replay is rejected. Receipt creation then
queries the fixed public GitHub remote and requires the owner revision to be
reachable from `main` or an advertised release tag. Feature-branch tips are not
authority. It then size-bounds and compares both the
model blob and the catalog source blob at that same revision byte-for-byte with
the admitted bytes. A caller-configured `remote.origin.url` is not authority.

The clean-room release lifecycle is publish the new root first, then issue
receipts. Source, model, and exposure-ledger bytes enter `main`; once that exact
root is advertised, the content commit may receive receipts in a subsequent
commit. A release tag can add an immutable anchor, but it never replaces or
mutates receipt bytes. The current receipts were freshly issued against the new
clean-room root; none were inherited from the superseded repository history.
The receipt binds:

- data-owner repository and revision;
- source descriptor, release, and source digest;
- conversion contract and model digest;
- canonical file digest and schema;
- content-bound, byte-verified Git reference;
- resolved redistribution status.

Review-blocked and link-only inputs cannot receive an accepted receipt. A
`private_storage` probability-model source may use the narrow Storage receipt
route. It requires the stable `dnadesign.storage-object/v1` verifier, an
authoritative `dnadesign-data` private motif store produced by the advertised
converter revision, and exact `input` and `artifact` member digests for the
source report and canonical model. A path or reference string alone is not
authority. Receipt creation does not turn product dogfood into scientific
evidence; evidence acceptance remains study-owned.
