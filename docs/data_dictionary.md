# V2.1.1 data dictionary

Current run: `runs/audit/2026-07-10_v2.1.1/`.

## Primary strain table

`supervisor_sequence_availability.tsv` contains one row per current catalogue record.

| Column | Meaning |
|---|---|
| `ncppb_number` | NCPPB catalogue identifier |
| `ncppb_current_name` | Name in the saved NCPPB snapshot |
| `scope_status` | Current *Xanthomonas* or reclassified outside the genus |
| `confirmed_biosample_accessions` | Identity-confirmed BioSamples |
| `provisional_biosample_accessions` | Candidates excluded pending review |
| `assembly_accessions` | Taxonomy-gated confirmed Assemblies |
| `sra_run_accessions` | Taxonomy-gated confirmed SRA runs |
| `bioproject_accessions` | Confirmed sequence-provenance projects |
| `sequence_availability_category` | Best current public-data category |
| `identity_match_status` | Strain-identity evidence conclusion |
| `taxonomy_consistency_status` | NCPPB/NCBI name comparison |
| `taxonomy_review_required` | Whether classification requires review |
| `manual_review_required` | Whether any decision remains open |
| `review_reason` | Machine-readable review reason |

## Phylogeny input table

`phylogeny_input_manifest.tsv` also contains one row per current catalogue record.

| Column | Meaning |
|---|---|
| `preferred_resource_type` | `assembly`, `sra_wgs_reads` or `none` |
| `preferred_sequence_accessions` | Selected Assembly or SRA accessions |
| `phylogeny_readiness` | QC/read assembly/review state |
| `qc_required` | Whether downstream QC is required |
| `identity_review_required` | Identity gate |
| `taxonomy_review_required` | Taxonomy gate |
| `selection_block_reason` | Why no sequence was selected |

## Review and evidence tables

- `manual_review_queue.tsv`: one row per strain requiring review.
- `manual_review_candidates.tsv`: one row per strain-BioSample pair.
- `identifier_review_queue.tsv`: identifiers excluded from automatic search.
- `parser_review_queue.tsv`: clause/identifier collisions.
- `ncbi_query_plan.tsv` and `ncbi_query_execution.tsv`: query coverage.
- `biosample_candidates.tsv`: raw candidates; never use for confirmed-strain counts.
- `biosample_match_decisions.tsv`: accepted/rejected/review pair decisions.
- `linked_ncbi_records.tsv`: linked NCBI resources.
- `sequence_resource_manifest.tsv`: download and provenance records.
- `run_manifest.json`: workflow version, parameters, byte sizes and SHA-256 values.

## Historical baseline

`data/processed/ncppb_xanthomonas_master.csv` contains the earlier 898-record baseline and is retained only for regression. The current audit scope is the 897-row saved HTML snapshot.
