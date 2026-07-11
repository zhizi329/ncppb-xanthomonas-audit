# Three-species SNP phylogeny smoke test

This directory is the minimal retained record of the local reads-based smoke test. Raw/trimmed FASTQ, BAM, reference indexes, environments, and rebuildable intermediates were intentionally removed.

## Sampling

| Species | Selected paired Illumina runs | Completed stage |
|---|---:|---|
| *Xanthomonas campestris* | 42 | download and fastp QC |
| *Xanthomonas citri* | 37 | download, fastp QC, reference mapping, core alignment and IQ-TREE |
| *Xanthomonas euvesicatoria* | 66 | download and fastp QC |

Total: 145 runs.

## Retained evidence

- `selected_runs.tsv`: strain/run selection and ENA URLs;
- `ena_fastq_metadata.tsv`: ENA file size and MD5 metadata;
- `fastp_qc_summary.tsv`: QC summary for all 145 selected runs;
- `mapping_qc_summary_Xanthomonas_citri.tsv`: mapping coverage for 37 *X. citri* samples;
- `Xanthomonas_citri.core.fna.stats.tsv`: retained-site statistics;
- `Xanthomonas_citri.snp_distance_matrix.tsv`: pairwise SNP distances;
- `Xanthomonas_citri.treefile` and `.iqtree`: ML tree and IQ-TREE report;
- `itol/`: tree and metadata annotations for display.

This is a smoke test, not a frozen publication phylogeny. *X. campestris* and *X. euvesicatoria* did not reach the final ML-tree stage in this run.

All removed sequence payloads are recoverable from `selected_runs.tsv` and `ena_fastq_metadata.tsv`.
