# Data Dictionary

## V2.1 Supervisor and Audit Tables

The current validated outputs are in `results/v2_1_pipeline/`.

| File or column | Meaning |
|---|---|
| `supervisor_sequence_availability.tsv` | One current NCPPB catalogue strain per row, with confirmed and provisional NCBI links kept separate. |
| `confirmed_biosample_accessions` | BioSamples supported by a complete NCPPB number or formal collection identifier in a structured identity field. |
| `provisional_biosample_accessions` | Exact medium-code, title-only, or conflicting candidates retained for review but excluded from confirmed counts. |
| `identity_match_status` | Identity conclusion independent of taxonomy consistency. |
| `taxonomy_review_required` | `yes` when the NCBI organism name needs reconciliation; this does not automatically revoke a strong identity match. |
| `provisional_assembly_accessions`, `provisional_sra_run_accessions`, `provisional_bioproject_accessions` | Downstream links for review candidates, never mixed into confirmed sequence columns. |
| `strain_identifiers.tsv:identifier_strength` | `primary` for NCPPB number, `strong` for formal collection number, `medium` for sufficiently specific donor/isolate code, and `weak` for codes excluded from automatic search. |
| `biosample_candidates.tsv:identity_aliases` | NCBI identity values from alias attributes such as `isolate-name-alias`, `isolate_name_alias`, and `Other_CC`. |
| `ncbi_query_execution.tsv` | Per-query reported count, retrieved UID count, truncation state, warning count, and error state. |
| `v1_regression_recall_audit.tsv` | One row per V1 strain–BioSample pair, showing whether V2.1's new tracks rediscovered it and its current evidence decision. |

`source_snapshot_sha256` is optional and blank by default. The open-source workflow does not validate uploaded HTML against a fixed hash. It is populated only when the user explicitly runs with `--record-input-hash`.

V1 table definitions below are retained for historical compatibility.

## NCPPB Master Table

Each row should represent one NCPPB Xanthomonas strain record.

| Column | Meaning |
|---|---|
| `ncppb_number` | Standard NCPPB catalogue number, e.g. `NCPPB 1234`. |
| `ncppb_number_compact` | Compact number without space, e.g. `NCPPB1234`. Useful for search. |
| `current_name` | Current name shown in the NCPPB catalogue. |
| `name_as_received` | Name originally received by the collection, if available. |
| `alternative_names` | Synonyms, historical names, pathovar names, or other names. Use `;` to separate multiple values. |
| `pathovar` | Pathovar information if stated. |
| `host` | Host plant or source host, if available. |
| `country` | Country of origin, if available. |
| `other_collection_numbers` | Equivalent strain identifiers in other collections, if available. Use `;` to separate values. |
| `ncppb_catalogue_url` | URL for the NCPPB record. |
| `catalogue_sequence_links` | Sequence links already present in NCPPB catalogue, if any. |
| `notes` | Human notes about uncertainty or curation issues. |
| `sequencing_type` | Sequencing type explicitly shown in the NCPPB catalogue, if present. |
| `year_added` | Year the strain was added to NCPPB, if shown. |
| `type_strain_of_species` | Whether the catalogue marks this as a type strain of the species. |
| `pathotype_strain` | Whether the catalogue marks this as a pathotype strain. |
| `other_references` | Free-text references and collection notes from the NCPPB page. |
| `raw_record_text` | Full extracted text for the record, kept for traceability/debugging. |

## Important Rule

Do not delete original naming fields just because they look old or inconsistent. Old names may be exactly what appears in NCBI metadata.

## Strain Search Review Table

Output examples:

- `results/refactored_pipeline/07_search_result_review_898.tsv`
- `results/final_pipeline/strain_search_review.tsv`

Each row represents one NCPPB strain and summarises the current BioSample search result.

| Column | Meaning |
|---|---|
| `has_confirmed_biosample` | `yes` if at least one BioSample passed the exact strain-evidence filter. |
| `accepted_biosample_count` | Number of accepted evidence rows for the strain. One BioSample can occur more than once when multiple queries retrieve it; use `accepted_biosample_accessions` for unique accessions. |
| `accepted_biosample_accessions` | Accepted BioSample accessions, separated by `;`. |
| `matched_identifiers` | NCPPB number or equivalent collection identifiers that supported accepted matches. |
| `matched_identifier_types` | Identifier evidence class, e.g. `ncppb_number` or `other_reference_identifier`. |
| `review_candidate_count` | Number of non-accepted candidates retained for review. |
| `conflict_rows` | Candidate rows containing a conflicting NCPPB number. |
| `taxon_only_rows` | Candidate rows matching only the taxon/species level, without exact strain evidence. |
| `accepted_needs_review_count` | Accepted rows flagged by a secondary audit and requiring curator review. |
| `search_result_review_status` | Strain-level status: `confirmed_biosample_match`, `manual_review_required`, or `no_confirmed_match_yet`. |
| `review_priority` | Practical review category, with `P1` highest priority. |
| `review_note` | Short explanation for the status and priority. |

## Sequence Availability Table

Output examples:

- `results/refactored_pipeline/11_supervisor_sequence_availability.tsv`
- `results/final_pipeline/sequence_availability.tsv`

Each row represents one NCPPB strain and reports public NCBI sequence-data availability linked through confirmed BioSample records.

| Column | Meaning |
|---|---|
| `sequence_data_category` | Best current category: complete genome, chromosome-level assembly, draft assembly, raw reads only, BioSample metadata only, ambiguous/manual review, or no confirmed sequence data. |
| `confirmed_biosample_count` | Number of unique confirmed BioSample accessions for the strain after deduplication. |
| `biosample_accessions` | Confirmed BioSample accessions used as the link point. |
| `biosample_organisms` | Organism names returned by NCBI BioSample. |
| `biosample_taxids` | NCBI BioSample taxon identifiers returned with the confirmed BioSample metadata, if available. |
| `taxonomic_consistency_status` | Script-generated comparison between NCPPB names and NCBI BioSample organism names. |
| `taxonomic_consistency_note` | Short explanation supporting the taxonomic consistency status. |
| `has_assembly` | `yes` if a linked NCBI Assembly record was found. |
| `assembly_accessions` | Linked Assembly accessions, e.g. `GCA_...` or `GCF_...`. |
| `assembly_levels` | NCBI assembly status such as `Complete Genome`, `Chromosome`, `Scaffold`, or `Contig`. |
| `has_raw_reads` | `yes` if linked SRA/raw-read metadata was found. |
| `run_accessions` | Linked SRA run accessions, e.g. `SRR...`, `ERR...`, or `DRR...`. |
| `sra_library_strategies` | SRA library strategy values, usually `WGS` for this project. |
| `needs_manual_review` | `yes` if the strain-level search review status is unresolved or ambiguous. |
| `ncbi_metadata_status` | Status of the NCBI metadata expansion step for that row. |

## Manual Review Queue

Output examples:

- `results/refactored_pipeline/12_manual_review_queue.tsv`
- `results/final_pipeline/manual_review_queue.tsv`

Each row is a strain that requires manual review before final counts are frozen.

| Column | Meaning |
|---|---|
| `review_order` | Suggested review order, sorted by priority. |
| `review_priority` | Priority inherited from the strain search review table. |
| `accepted_biosample_accessions` | Currently accepted BioSamples, if any. |
| `accepted_needs_review_accessions` | Accepted BioSamples that should be checked before being counted. |
| `secondary_candidate_biosample_accessions` | Non-accepted candidate BioSamples that may explain conflicts or false positives. |
| `accepted_biosample_urls` / `secondary_candidate_biosample_urls` | Direct NCBI BioSample links for manual inspection. |
| `assembly_urls` / `run_urls` | Direct NCBI Assembly and SRA links for accepted sequence records. |
| `manual_review_focus` | What the reviewer should pay attention to. |
| `recommended_action` | Script-generated recommendation before human confirmation. |
| `review_question` | The specific question to answer during manual review. |
| `reviewer_decision` | Blank column for the final human decision. |
| `reviewer_notes` | Blank column for notes supporting the decision. |

Recommended `reviewer_decision` values:

- `keep_current`: retain the current sequence-data category after manual inspection.
- `downgrade_no_confirmed_match`: do not count the candidate as a confirmed strain-level match.
- `pending_manual_review`: leave the row unresolved.

## Final Audit Table

Output examples:

- `results/refactored_pipeline/13_final_audit_table.tsv`
- `results/final_pipeline/final_audit_table.tsv`

This table starts from the sequence availability table and adds final decision columns from the manual-review queue.

| Column | Meaning |
|---|---|
| `final_audit_status` | Final decision status, e.g. `algorithmic_no_review_needed`, `accepted_after_manual_review`, `downgraded_after_manual_review`, or `pending_manual_review`. |
| `final_sequence_data_category` | Category to use in final summary counts after applying manual-review decisions. |
| `final_needs_manual_review` | `yes` if the row is still unresolved. |
| `manual_reviewer_decision` | Human decision copied from `reviewer_decision`. |
| `manual_reviewer_notes` | Human notes copied from `reviewer_notes`. |
| `manual_review_priority` | Review priority inherited from the manual-review queue. |
| `manual_recommended_action` | Script recommendation that was available to the reviewer. |

The table is only frozen when `final_needs_manual_review` is `no` for every row.

## Summary Figures

Output examples:

- `results/refactored_pipeline/14_summary_figures/sequence_category_counts.tsv`
- `results/refactored_pipeline/14_summary_figures/sequence_category_counts.svg`
- `results/refactored_pipeline/14_summary_figures/sequence_data_presence_counts.tsv`
- `results/refactored_pipeline/14_summary_figures/sequence_data_presence.svg`
- `results/refactored_pipeline/14_summary_figures/taxonomic_consistency_counts.tsv`
- `results/refactored_pipeline/14_summary_figures/taxonomic_consistency_counts.svg`
- `results/refactored_pipeline/14_summary_figures/manual_review_priority_counts.tsv`
- `results/refactored_pipeline/14_summary_figures/manual_review_priority_counts.svg`

These files are generated from the interim or final audit tables. They summarise
metadata-audit categories and public-data presence only; they are not
phylogenetic trees or sequence-quality analyses.

| Column | Meaning |
|---|---|
| `sequence_data_category` | Human-readable audit category used in the category-count figure. |
| `metric` | Human-readable public-data presence metric, such as linked Assembly or linked SRA/raw reads. |
| `review_priority` | Manual-review priority category used in the manual-review figure. |
| `count` | Number of NCPPB strain rows in that category or metric. |
