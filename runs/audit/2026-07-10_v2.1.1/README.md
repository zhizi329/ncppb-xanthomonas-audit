# NCPPB-NCBI audit V2.1.1 - 2026-07-10 (archived)

Status: archived validated interim run; manual biological review is not frozen. This run is retained as provenance and is not the final submission denominator.

NCBI evidence timestamp: 2026-07-01. The saved evidence was recomputed with the V2.1.1 taxonomy/pathovar safety gate on 2026-07-10.

## Start here

| File | Use |
|---|---|
| `supervisor_sequence_availability.tsv` | One-row-per-current-strain table for this archived run |
| `phylogeny_input_manifest.tsv` | Preferred sequence source and block/readiness status for each strain |
| `manual_review_queue.tsv` | 92 strains requiring identity and/or taxonomy review |
| `run_summary.md` | Human-readable run statistics |
| `run_manifest.json` | Workflow version, parameters, timestamps, sizes and SHA-256 values |

## Supporting evidence tables

| Group | Files |
|---|---|
| Catalogue provenance | `catalogue_strains.tsv`, `catalogue_snapshot_diff.tsv`, `other_reference_clauses.tsv` |
| Identifier evidence | `strain_identifiers.tsv`, `identifier_review_queue.tsv`, `parser_review_queue.tsv` |
| NCBI query audit | `ncbi_query_plan.tsv`, `ncbi_query_execution.tsv`, `biosample_candidates.tsv` |
| Match decisions | `biosample_match_decisions.tsv`, `manual_review_candidates.tsv` |
| Linked resources | `linked_ncbi_records.tsv`, `sequence_resource_manifest.tsv`, `bioproject_mapping.tsv` |
| Historical regression | `v1_v2_comparison.tsv`, `v1_v2_accession_changes.tsv`, `v1_regression_recall_audit.tsv` |
| Explorer-style export | `explorer_strain_catalogue.tsv` |

Do not quote headline counts from candidate, linked-record, or historical regression tables. Those tables contain multiple records per strain or a different snapshot scope.
