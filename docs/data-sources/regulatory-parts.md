# Regulatory Parts And TF-Target Data

For typed Motif Balance inputs and binding-site export contracts, start at
[Motif source exports](../motif-sources/README.md).

RegulonDB, EcoCyc, and primary-literature TF-target datasets that support regulatory-source discovery and promoter-context work.

### Transcription Factor (TF)–Target Gene Interactions

#### DNA affinity purification sequencing (DAP-seq)

- **O'Malley *et al.***
  - **Title**: *Persistence and plasticity in bacterial gene regulation*
  - **DOI**: [10.1038/s41592-021-01312-2](https://www.nature.com/articles/s41592-021-01312-2)
  - **Association**: TF-gene interactions
  - **Comments**: Report a high-throughput approach for characterizing TF–target gene interactions across species and its application to 354 TFs across 48 bacteria, generating 17,000 genome-wide binding maps.
  - **Format**: *E. coli* TF DNA binding motifs in MEME format from Supplementary Data 2.

#### Mechanically induced trapping of molecular interactions (MITOMI)

- **Westmann *et al.***
  - **Title**: *The highly rugged yet navigable regulatory landscape of the bacterial transcription factor TetR*
  - **DOI**: [10.1038/s41467-024-54723-y](https://www.nature.com/articles/s41467-024-54723-y)
  - **Association**: TetR binding specificity
  - **Comments**: Stores the wild-type TetR Position Weight Matrix (PWM) from the EPF-Lausanne 2011 iGEM MITOMI page for TetO single-substitution binding-energy changes, cited here alongside the recent TetR regulatory landscape paper.
  - **Format**: Wild-type TetR PWM as TSV plus lightweight provenance README.

#### Promoter responses to TF perturbation sequencing (PPTP-seq)

- **Han *et al.***
  - **Title**: *Genome-wide promoter responses to CRISPR perturbations of regulators reveal regulatory networks in Escherichia coli*
  - **DOI**: [10.1038/s41467-023-41572-4](https://www.nature.com/articles/s41467-023-41572-4)
  - **Association**: TF-gene interactions
  - **Comments**: Systematically measured the activity of 1372 *E. coli* promoters under single knockdown of 183 TF genes, illustrating more than 200,000 possible TF-gene responses in one experiment.
  - **Format**: Supplementary Data 6 and 7.

#### Chromatin immunoprecipitation exonuclease sequencing (ChIP-exo)

- **Choudhary *et al.***
  - **Title**: *Elucidation of Regulatory Modes for Five Two-Component Systems in Escherichia coli Reveals Novel Relationships*
  - **DOI**: [10.1128/mSystems.00980-20](https://doi.org/10.1128/mSystems.00980-20)
  - **Association**: TF-gene interactions (two-component response regulators)
  - **Comments**: ChIP-exo + RNA-seq + ICA to refine regulons for five response regulators in *E. coli* K-12 MG1655. This dataset hydrates the BaeR ChIP-exo peak coordinates from the supplemental table into strand-aware binding-site sequences.
  - **Format**: ChIP-exo peak table (supplemental Data Set S2), BaeR sheet → exported as TSV/FASTA binding sites.

### Regulatory Parts

- **EcoCyc datasets**
  - **Promoters**: SmartTable of all promoters in *E. coli* K-12, curated from release 28.
  - **TF binding sites**: SmartTable of all TFBSs in *E. coli* K-12, curated from release 28.
  - **Regulatory network**: Regulatory network from EcoCyc's Pathway/Genome Database, which has connections between transcription factors and downstream regulatees.

- **RegulonDB datasets**
  - **Promoter datasets**: Promoters curated from RegulonDB, releases 11 and 13.
  - **Binding sites datasets**: TF binding sites from ChIP‐seq/footprinting.
  - **High‐throughput experimental datasets**: Additional promoter characterization datasets.
