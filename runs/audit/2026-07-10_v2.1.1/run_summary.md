# NCPPB audit V2.1 run summary

## Local input and parser

- Current HTML snapshot records: 897
- Records missing relative to V1: 1 (NCPPB 4416)
- Other-reference clauses: 1585
- Clause types: collection_list=328; donor_reference=405; isolated_by=641; source_of_isolate=211
- Clause risk levels: high=25; low=328; medium=1232
- Parser review queue rows: 18
- Actionable identifier review rows: 232
- Searchable Other-reference identifiers: 1164

## Two-track NCBI query plan

- Query rows: 1376
- Query tracks: ncppb_number=903; other_references=473
- Query tiers: exact_full_identifier=897; expected_genus=442; expected_genus:Pseudomonas=1; expected_genus:Sphingomonas=1; expected_genus:Stenotrophomonas=5; expected_genus:Xanthomonas=23; expected_genus:Xylophilus=6; unfiltered_fallback=1
- The NCPPB-number track combines a broad trusted-prefix harvest with one literal full-identifier query per catalogue strain. Full forms such as `NCPPB 45`, `NCPPB45`, and `NCPPB:45` are OR-combined and never emitted as independent prefix/number `AND` terms.
- Formal Other-reference collection numbers use prefix harvest plus complete local identifier validation; medium donor/isolate codes are candidate-only and cannot be auto-accepted.

## NCBI matching and linked records

- Candidate decisions: 874
- Decisions: accept=533; reject=301; review=40
- Evidence classes: no_exact_identifier=298; separated_query_terms_only=3; structured_exact_identifier=566; unstructured_exact_identifier=7
- Supervisor rows: 897
- Sequence categories: ambiguous_needs_review=25; biosample_metadata_only_no_linked_sequence=2; chromosome_level_assembly_available=3; complete_genome_available=106; draft_assembly_available=153; no_confirmed_public_data=512; raw_reads_only=46; taxonomy_review_required_before_sequence_use=50
- Scope status: current_xanthomonas=884; reclassified_outside_xanthomonas=13
- Pathovar comparison: not_applicable_no_expected_pathovar=125; observed_pathovar_unresolved=385; pathovar_mismatch=26; same_pathovar=338
- Strains with changed confirmed BioSample accessions versus V1: 34
