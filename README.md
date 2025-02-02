### About
This repository contains datasets from primary literature, as well as RegulonDB and EcoCyc, related to transcriptional regulation, proteome allocation, promoter engineering, genome streamlining, and more.  

### Usage
After cloning this repository, edit the relevant configuration paths in **`dnadesign`** or **`deg2tfbs`** so that they point here (i.e., to the local path where these data folders live).

---

### Data Sources by Category

Below is a breakdown of the major datasets included, grouped by broad themes.  Each entry includes its **folder name**, **title**, **DOI**, thematic **association** (e.g., “stringent response,” “antibiotic stress response”), and **comments** (blurb on article findings or data types).

---

### Comparative Omics (RNA‐seq, Absolute Proteomics)  
Most of these datasets compare omics readouts between a single “target” and “reference” condition, enabling the identification of up- and down-regulated genes. Some studies provide full raw data, which lets us reproduce results, apply custom thresholds, and isolate differentially expressed genes ourselves (as is done in **`deg2tfbs`**). Other articles do not share raw data but instead list up- and down-regulated genes directly, in which case we simply import those gene sets into **`deg2tfbs`** to identify the associated transcription factors and their DNA-binding sites. These binding sites can then later be used in **`dnadesign`**.

#### Diverse Media Conditions

- **Mori *et al.***  
  - **Title**: *From coarse to fine: the absolute Escherichia coli proteome under diverse growth conditions*  
  - **DOI**: [10.15252/msb.20209536](https://www.embopress.org/doi/full/10.15252/msb.20209536)  
  - **Association**: Proteomic allocation  
  - **Comments**: Quantification of >2,000 proteins in *E. coli* across 60+ growth conditions (nutrient limitations, stress, etc.).
  - **Format**: Full source dataset available ✅
 
- **Schmidt *et al.***  
  - **Title**: *The quantitative and condition-dependent Escherichia coli proteome*  
  - **DOI**: [10.1038/nbt.3418](https://www.nature.com/articles/nbt.3418)  
  - **Association**: Ratio of TF proteins in given environments  
  - **Comments**: Table S6 includes global absolute abundances, providing a resource for stoichiometric modeling of TF:DNA interactions.
  - **Format**: Full source dataset available ✅

#### The Stringent Response

- **Durfee *et al.***  
  - **Title**: *Transcription profiling of the stringent response in Escherichia coli*  
  - **DOI**: [10.1128/JB.01092-07](https://journals.asm.org/doi/10.1128/jb.01092-07)  
  - **Association**: Stringent response  
  - **Comments**: Conducted a transcriptomic study by inducing ppGpp accumulation; curated a list of differentially expressed genes within 5 minutes of stringent response onset.
  - **Format**: List of up- and down-regulated genes available.

- **Fragoso‐Jimenez *et al.***  
  - **Title**: *Glucose consumption rate-dependent transcriptome profiling of Escherichia coli provides insight on performance as microbial factories*  
  - **DOI**: [10.1186/s12934-022-01909-y](https://microbialcellfactories.biomedcentral.com/articles/10.1186/s12934-022-01909-y)  
  - **Association**: Carbon uptake / diauxic growth  
  - **Comments**: RNA‐seq on *E. coli* with attenuated growth and substrate‐uptake rates; identifies negative correlations (genes up while uptake down).
  - **Format**: List of up- and down-regulated genes available.

- **Franchini *et al.* (a), (b)**  
  - **DOIs**: [10.1371/journal.pone.0133793](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0133793) and [10.1099/mic.0.28939-0](https://www.microbiologyresearch.org/content/journal/micro/10.1099/mic.0.28939-0)  
  - **Association**: Stringent response under glucose limitation  
  - **Comments**: Transcriptomic studies in *E. coli* ΔrpoS and Δcya mutants under glucose‐limited continuous culture (Franchini a).  Also a long‐term adaptation dataset (Franchini b).
  - **Format**: List of up- and down-regulated genes available.

- **Gummesson *et al.***  
  - **Title**: *Valine‐Induced Isoleucine Starvation in E. coli Studied by Spike‐In Normalized RNA Sequencing*  
  - **DOI**: [10.3389/fgene.2020.00144](https://www.frontiersin.org/journals/genetics/articles/10.3389/fgene.2020.00144/full)
  - **Association**: Stringent response  
  - **Comments**: PC1/PC2 scores for all genes and a list of 506 genes ≥2.0 fold up after 80 min of isoleucine starvation, plus top 100 most strongly activated genes.
  - **Format**: Full source dataset available ✅

- **Houser *et al.***  
  - **Title**: *Controlled Measurement and Comparative Analysis of Cellular Components in E. coli*  
  - **DOI**: [10.1371/journal.pcbi.1004400](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1004400)
  - **Association**: Stringent response  
  - **Comments**: Detailed time‐course characterization (two weeks) of *E. coli* growth and starvation.  Supplemental Table 4 highlights RNAs significantly changing through starvation.
  - **Format**: List of up- and down-regulated genes available.


- **Lu *et al.***  
  - **Title**: *Genome-wide transcriptional responses of Escherichia coli to glyphosate, a potent inhibitor of the shikimate pathway enzyme 5-enolpyruvylshikimate-3-phosphate synthase*  
  - **DOI**: [10.1039/C2MB25374G](https://doi.org/10.1039/C2MB25374G)  
  - **Association**: Stringent response  
  - **Comments**: Transcriptome analysis of *E. coli* exposed to 200 mM glyphosate revealed differential expression of 1,040 genes (~23% of the genome), highlighting wide-reaching metabolic stress.
  - **Format**: List of up- and down-regulated genes available.

- **Sanchez‐Vazquez *et al.***  
  - **Title**: *Genome-wide effects on Escherichia coli transcription from ppGpp binding to its two sites on RNA polymerase*  
  - **DOI**: [10.1073/pnas.1819682116](https://pubmed.ncbi.nlm.nih.gov/30971496/)
  - **Association**: Stringent response  
  - **Comments**: RNA‐seq of *E. coli* with and without ppGpp‐binding sites on RNAP; extensive gene expression changes at 5–10 min.
  - **Format**: Full source dataset available ✅

- **Traxler *et al.***  
  - **Title**: *Discretely calibrated regulatory loops controlled by ppGpp partition gene induction across the 'feast to famine' gradient in Escherichia coli*  
  - **DOI**: [10.1111/j.1365-2958.2010.07498.x](https://pubmed.ncbi.nlm.nih.gov/21299642/)
  - **Association**: Stringent response  
  - **Comments**: Identified gene sets requiring ppGpp, Lrp, and RpoS for induction across the “feast to famine” gradient.

- **Wu *et al.***  
  - **Title**: *Enzyme expression kinetics by Escherichia coli during transition from rich to minimal media depends on proteome reserves*  
  - **DOI**: [10.1038/s41564-022-01310-w](https://www.nature.com/articles/s41564-022-01310-w)
  - **Association**: Nutrient shift protein abundances  
  - **Comments**: Proteome allocation in rich vs. minimal media, plus transitions. Supplementary Table 9 has proteomic fractions.
  - **Format**: Full source dataset available ✅

- **Zhu *et al.***  
  - **Title**: *Stringent response ensures the timely adaptation of bacterial growth to nutrient downshift*  
  - **DOI**: [10.1038/s41467-023-36254-0](https://www.nature.com/articles/s41467-023-36254-0)
  - **Association**: Stringent response  
  - **Comments**: Proteomic profiling of >2500 proteins during nutrient downshift in wild‐type and *relA*‐deficient strains.
  - **Format**: Full source dataset available ✅

#### Metabolic Burden

- **Ceroni *et al.***  
  - **Title**: *Burden‐driven feedback control of gene expression*  
  - **DOI**: [10.1038/nmeth.4635](https://www.nature.com/articles/nmeth.4635)
  - **Association**: Metabolic burden  
  - **Comments**: RNA‐seq plus in vivo assays identify major transcriptional changes when strong synthetic constructs are over‐expressed.
  - **Format**: Full source dataset available ✅

- **Rajacharya *et al.***  
  - **Title**: *Proteomics and metabolic burden analysis to understand the impact of recombinant protein production in E. coli*  
  - **DOI**: [10.1038/s41598-024-63148-y](https://www.nature.com/articles/s41598-024-63148-y)
  - **Association**: Metabolic burden  
  - **Comments**: Investigated wild type vs. recombinant strains (inducing recombinant protein acyl-ACP reductase at various time points) via proteomics to track expression burden.
  - **Format**: Full source dataset available ✅

#### Membrane Stress and Fatty Acid Production

- **Emani *et al.***  
  - **Title**: *Periplasmic stress contributes to a trade-off between protein secretion and cell growth in Escherichia coli Nissle 1917*  
  - **DOI**: [10.1093/synbio/ysad013](https://academic.oup.com/synbio/article/8/1/ysad013/7234012)
  - **Association**: Protein secretion  
  - **Comments**: RNA‐seq used to probe growth–secretion trade‐offs in *E. coli* Nissle 1917 secreting sfGFP via the curli system.
  - **Format**: Partial source dataset available.

- **Vazulka *et al.***  
  - **Title**: *RNA-seq reveals multifaceted gene expression response to Fab production in Escherichia coli fed-batch processes with particular focus on ribosome stalling*  
  - **DOI**: [10.1186/s12934-023-02278-w](https://doi.org/10.1186/s12934-023-02278-w)  
  - **Association**: Fab production  
  - **Comments**: Characterized the gene expression response in *E. coli* BL21(DE3) and HMS174(DE3) to periplasmic Fab expression via fed-batch RNA‐seq.
  - **Format**: List of up- and down-regulated genes available.

#### Antibiotic Stress

- **Bie *et al.***  
  - **Title**: *Comparative Analysis of Transcriptomic Response of Escherichia coli K-12 MG1655 to Nine Representative Classes of Antibiotics*  
  - **DOI**: [10.1128/spectrum.00317-23](https://journals.asm.org/doi/10.1128/spectrum.00317-23)
  - **Association**: Antibiotic response  
  - **Comments**: Performed transcriptomic analysis on how E. coli responds to nine representative classes of antibiotics (tetracycline, mitomycin C, imipenem, ceftazidime, kanamycin, ciprofloxacin, polymyxin E, erythromycin, and chloramphenicol).
  - **Format**: Full source dataset available ✅

- **Deter *et al.***  
  - **Title**: *Antibiotic tolerance is associated with a broad and complex transcriptional response in E. coli*  
  - **DOI**: [10.1038/s41598-021-85509-7](https://www.nature.com/articles/s41598-021-85509-7)
  - **Association**: Ampicillin resistance  
  - **Comments**: Generated RNA-seq data on both antibiotic-treated and -untreated populations emerging from stationary phase.
  - **Format**: Full source dataset available ✅

- **Radzikowski *et al.***  
  - **Title**: *Bacterial persistence is an active σS stress response to metabolic flux limitation*  
  - **DOI**: [10.15252/msb.20166998](https://www.embopress.org/doi/full/10.15252/msb.20166998)
  - **Association**: Stringent response  
  - **Comments**: Developed and verified a model linking metabolic flux collapse to *E. coli* persistence under severe stress.
  - **Format**: Full source dataset available ✅

#### Heat Shock Response

- **Kim *et al.***  
  - **Title**: *Heat-responsive and time-resolved transcriptome and metabolome analyses of Escherichia coli uncover thermo-tolerant mechanisms*  
  - **DOI**: [10.1038/s41598-020-74606-8](https://doi.org/10.1038/s41598-020-74606-8)  
  - **Association**: Heat shock response  
  - **Comments**: Applied RNA‐seq to capture early, middle, and late stages of heat stress (2 min–40 h), illuminating initiation, adaptation, and phenotypic plasticity phases in *E. coli*.
  - **Format**: Full source dataset available ✅

- **Zhang *et al.***  
  - **Title**: *Heat-Shock Response Transcriptional Program Enables High-Yield and High-Quality Recombinant Protein Production in Escherichia coli*  
  - **DOI**: [10.1021/cb5004477](https://doi.org/10.1021/cb5004477)  
  - **Association**: Heat shock response  
  - **Comments**: Demonstrated that a σ^32‐I54N HSR-like reprogrammed proteostasis network can boost soluble, folded, and functional recombinant proteins
  - **Format**: List of up-regulated genes (no down-regulated) available.

#### Phage Shock Response

- **Jovanovic *et al.***  
  - **Title**: *Induction and Function of the Phage Shock Protein Extracytoplasmic Stress Response in Escherichia coli*  
  - **DOI**: [10.1074/jbc.M602323200](https://doi.org/10.1074/jbc.M602323200)  
  - **Association**: Phage shock response  
  - **Comments**: Generated a microarray dataset comparing *E. coli* strains with and without Psp-inducing protein IV secretin stress.

The module identifies up- and down-regulated genes using IQR-based outlier detection 
applied to the log 'Fold regulation' distribution from a microarray dataset.
  - **Format**: List of up- and down-regulated genes available.

---

#### PRECISE‐2K (High‐Coverage RNA‐seq Compendium)  
- **Lamoureux *et al.***  
  - **Title**: *PRECISE 2.0 - an expanded high-quality RNA-seq compendium for Escherichia coli K-12 reveals high-resolution transcriptional regulatory structure*  
  - **DOI**: [10.1101/2021.04.08.439047](https://www.biorxiv.org/content/10.1101/2021.04.08.439047v1)
  - **Association**: Independent component analysis  
  - **Comments**: A set of 278 standardized RNA‐seq datasets for *E. coli* K‐12 MG1655; used ICA to define 218 iModulons describing global regulatory structure.

---

#### Genome Streamlining & Reduced‐Genome Strains  
- **Baumgart *et al.***  
  - **Title**: *Corynebacterium glutamicum Chassis C1 Building and Testing a Novel Platform Host for Synthetic Biology and Industrial Biotechnology*  
  - **DOI**: [10.1021/acssynbio.7b00261](https://pubs.acs.org/doi/10.1021/acssynbio.7b00261)
  - **Association**: Genome streamlining  
  - **Comments**: Created 26 genome‐reduced *C. glutamicum* strains with minimal fitness costs.

- **Lastiri‐Pancardo *et al.***  
  - **Title**: *A quantitative method for proteome reallocation using minimal regulatory interventions*  
  - **DOI**: [10.1038/s41589-020-0593-y](https://www.nature.com/articles/s41589-020-0593-y)
  - **Association**: Proteome allocation  
  - **Comments**: Designed ReProMin to remove TFs in *E. coli* that maximizes release of resources for cell growth or synthetic usage.

- **Loffler *et al.***  
  - **Title**: *Engineering E. coli for large-scale production - Strategies considering ATP expenses and transcriptional responses*  
  - **DOI**: [10.1016/j.ymben.2016.06.008](https://pubmed.ncbi.nlm.nih.gov/27378496/)
  - **Association**: Cell maintenance costs  
  - **Comments**: Identified top 20 energy‐consuming genes during large‐scale production; relevant to stringent response economics.

- **Posfai *et al.***  
  - **Title**: *Emergent properties of reduced‐genome Escherichia coli*  
  - **DOI**: [10.1126/science.1126439](https://www.science.org/doi/10.1126/science.1126439)
  - **Association**: Genome streamlining  
  - **Comments**: Reduced the *E. coli* genome by ~20%; listed all deleted genes in strain MGS43.

- **Ziegler *et al.***  
  - **Title**: *Transcriptional profiling of the stringent response mutant strain E. coli SR reveals enhanced robustness to large-scale conditions*  
  - **DOI**: [10.1016/j.ymben.2021.05.011](https://pubmed.ncbi.nlm.nih.gov/34098100/)
  - **Association**: Genome streamlining  
  - **Comments**: Provided list of genes deleted in strain RM214, which showed a lower maintenance coefficient under simulated large‐scale conditions.

---

### Promoter/Regulatory Element Datasets

- **EcoCyc data**  
  *In this repository, EcoCyc‐derived gene annotations, regulatory interactions, and functional groupings are stored for integration with `deg2tfbs` and `dnadesign`.*
  
- **RegulonDB data**  
  - **Promoter datasets**: Promoters curated from RegulonDB, releases 11 and 13.
  - **Binding sites datasets**: TF binding sites from ChIP‐seq/footprinting.  
  - **High‐throughput experimental datasets**: Additional promoter characterization datasets.

---

#### Promoter Engineering

- **Hernandez *et al.***  
  - **Title**: *PromoterLCNN: A Light CNN-Based Promoter Prediction and Classification Model*  
  - **DOI**: [10.3390/genes13071126](https://www.mdpi.com/2073-4425/13/7/1126)
  - **Association**: Promoter prediction  
  - **Comments**: Built a multiclass CNN for promoter identification/classification using a RegulonDB v9.3 dataset.

- **Johns *et al.***  
  - **Title**: *Metagenomic mining of regulatory elements enables programmable species-selective gene expression*  
  - **DOI**: [10.1038/nmeth.4633](https://www.nature.com/articles/nmeth.4633)
  - **Association**: Promoter prediction  
  - **Comments**: Large‐scale analysis of diverse bacterial regulatory sequences for species‐selective gene expression.

- **Kosuri *et al.***  
  - **Title**: *Composability of regulatory sequences controlling transcription and translation in Escherichia coli*  
  - **DOI**: [10.1073/pnas.1301301110](https://www.pnas.org/doi/10.1073/pnas.1301301110)
  - **Association**: Promoter engineering 
  - **Comments**: Synthesized 12,563 combinations of common promoters and ribosome binding sites and simultaneously measured DNA, RNA, and protein levels from the entire library. 

- **Thomason *et al.***  
  - **Title**: *Global Transcriptional Start Site Mapping Using Differential RNA Sequencing Reveals Novel Antisense RNAs in Escherichia coli*  
  - **DOI**: [10.1128/JB.02096-14](https://journals.asm.org/doi/10.1128/jb.02096-14)
  - **Association**: Transcription start site mapping  
  - **Comments**: dRNA‐seq approach to distinguish primary vs. processed transcripts, with an automated TSS‐calling algorithm.

- **Sun Yim *et al.***  
  - **Title**: *Multiplex transcriptional characterizations across diverse bacterial species using cell-free systems*  
  - **DOI**: [10.15252/msb.20198875](https://www.embopress.org/doi/full/10.15252/msb.20198875)
  - **Association**: Promoter prediction  
  - **Comments**: Used active lysates from 10 bacterial species to measure transcription activities of thousands of regulatory sequences.

- **Yu *et al.***  
  - **Title**: *Multiplexed characterization of rationally designed promoter architectures deconstructs combinatorial logic for IPTG-inducible systems*  
  - **DOI**: [10.1038/s41467-020-20094-3](https://www.nature.com/articles/s41467-020-20094-3)
  - **Association**: Promoter characterization  
  - **Comments**: Profiled expression of 8269 IPTG‐inducible promoters that vary RNAP and LacI‐binding sites.

- **Urtecho *et al.***  
  - **Title**: *Systematic Dissection of Sequence Elements Controlling σ70 Promoters Using a Genomically Encoded Multiplexed Reporter Assay in Escherichia coli*  
  - **DOI**: [10.1021/acs.biochem.7b01069](https://pubs.acs.org/doi/10.1021/acs.biochem.7b01069)
  - **Association**: Promoter characterization  
  - **Comments**: A 10,898‐variant library dissecting −35, −10, UP elements, and spacers to evaluate σ70‐dependent expression.

- **LaFleur *et al.***  
  - **Title**: *Automated model-predictive design of synthetic promoters to control transcriptional profiles in bacteria*  
  - **DOI**: [10.1038/s41467-022-32829-5](https://www.nature.com/articles/s41467-022-32829-5)
  - **Association**: Promoter characterization  
  - **Comments**: Combined high‐throughput assays, biophysical models, and machine learning to design 34k+ promoters.

- **Hossain *et al.***  
  - **Title**: *Automated design of thousands of nonrepetitive parts for engineering stable genetic systems*  
  - **DOI**: [10.1038/s41587-020-0584-2](https://www.nature.com/articles/s41587-020-0584-2)
  - **Association**: Promoter characterization  
  - **Comments**: Created/characterized 4,350 *E. coli* promoters and 1,722 yeast promoters, achieving large dynamic range.

---

#### Other Curated Literature

- **Baba *et al.***  
  - **Title**: *Construction of Escherichia coli K‐12 in‐frame, single‐gene knockout mutants: The Keio collection*  
  - **DOI**: [10.1038/msb4100050](https://www.embopress.org/doi/full/10.1038/msb4100050)
  - **Association**: Keio collection  
  - **Comments**: Systematic single‐gene deletions in *E. coli* K‐12; standard for genetic knockouts.

- **Freddolino *et al.***  
  - **Title**: *Dynamic landscape of protein occupancy across the Escherichia coli chromosome*  
  - **DOI**: [10.1371/journal.pbio.3001306](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3001306)
  - **Association**: Protein occupancy on chromosome  
  - **Comments**: Parallel monitoring of DNA‐binding protein occupancy states under various genetic and environmental perturbations.

- **Gao *et al.***  
  - **Title**: *A balancing act in transcription regulation by response regulators titration of transcription factor activity by decoy DNA binding sites*  
  - **DOI**: [10.1093/nar/gkab935](https://academic.oup.com/nar/article/49/20/11537/6406471)
  - **Association**: TF protein/TFBS ratio  
  - **Comments**: Computed TF/TFBS ratios in 19 growth conditions, highlighting potential “decoy” DNA effects.

- **Kumar *et al.***  
  - **Title**: *Amino acid supplementation for enhancing recombinant protein production in E. coli*  
  - **DOI**: [10.1002/bit.27371](https://analyticalsciencejournals.onlinelibrary.wiley.com/doi/abs/10.1002/bit.27371)
  - **Association**: Universal stress proteins  
  - **Comments**: Discusses the accumulation of universal stress proteins in *E. coli* when encountering any growth arrest.

- **McKee *et al.***  
  - **Title**: *Manipulation of the carbon storage regulator system for metabolite remodeling and biofuel production in Escherichia coli*  
  - **DOI**: [10.1186/1475-2859-11-79](https://microbialcellfactories.biomedcentral.com/articles/10.1186/1475-2859-11-79)
  - **Association**: CsrA‐regulated genes  
  - **Comments**: Generated hundreds of predicted CsrA binding sites from shotgun proteomics.

- **Peebo *et al.***  
  - **Title**: *Proteome reallocation in Escherichia coli with increasing specific growth rate*  
  - **DOI**: [10.1039/C4MB00721B](https://pubs.rsc.org/en/content/articlelanding/2015/mb/c4mb00721b)
  - **Association**: Proteomic allocation  
  - **Comments**: Covariance analysis between protein‐expression costs and growth rate, identifying which proteins have highest “synthesis priority.”
  - **Format**: Full source dataset available ✅

- **Schink *et al.***  
  - **Title**: *Analysis of proteome adaptation reveals a key role of the bacterial envelope in starvation survival*  
  - **DOI**: [10.15252/msb.202211160](https://www.embopress.org/doi/full/10.15252/msb.202211160)
  - **Association**: Maintenance rate & bacterial envelope  
  - **Comments**: Trade‐offs between growth and survival to identify proteins correlated with *E. coli* death rates.
  - **Format**: Full source dataset available ✅

- **Youssef *et al.***  
  - **Title**: *Dynamic remodeling of Escherichia coli interactome in response to environmental perturbations*  
  - **DOI**: [10.1002/pmic.202200404](https://analyticalsciencejournals.onlinelibrary.wiley.com/doi/full/10.1002/pmic.202200404)
  - **Association**: Protein complex interaction remodeling  
  - **Comments**: Used co‐fractionation mass spectrometry across ten conditions to quantify ~2000 protein–protein interactions.

---

### Notes on Folder Organization
Each dataset above typically corresponds to its own folder (or subfolder), named in a way that reflects the first author, short title, or reference year.  Inside each folder, you may find:
- Raw or processed CSV/TSV files  
- Supplemental spreadsheets  
- Scripts or metadata describing how the data were sourced or filtered  

When using them in **`dnadesign`** or **`deg2tfbs`**, confirm that:
1. The folder structure aligns with your config file(s).  
2. You cite the appropriate DOIs and references if publishing results derived from these datasets.  

---

Last updated: 2025-01-27
@e-south
