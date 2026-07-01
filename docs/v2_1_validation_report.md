# V2.1 Full-Run Validation Report

## Conclusion

V2.1 completed a full run over 897 records in the current NCPPB catalogue HTML and passed the project validator. It does not claim absolute recall over every record that might exist in NCBI. It does eliminate the observed V2 truncation, phrase-index, alias-field and identifier-format failure modes, and it provides complete regression accounting against V1.

## Execution controls

- 1,376 unique planned queries;
- 1,376 successful query-execution records;
- zero truncated queries;
- zero BioSample candidate errors;
- zero Assembly/SRA/BioProject link errors;
- 897 supervisor rows;
- one catalogue difference relative to V1: NCPPB 4416 is absent from the current input and is not restored silently.

Phrase-index warnings remain recorded because NCBI may not index every spaced or punctuated variant. They are mitigated by compact variants, prefix harvests, local exact matching and V1 regression controls rather than being ignored.

## V1 regression accounting

V1 contains 552 strain–BioSample pairs. The diagnostic V2 search rediscovered 497; V2.1 rediscovered 535. Seventeen pairs required direct historical-accession inspection:

- six were rejected because no exact strain identifier was present;
- eleven remained provisional or title-only review candidates;
- zero accepted historical pairs depended on the historical-accession fallback.

All 516 V1 pairs that still satisfy the V2.1 acceptance rule were rediscovered by the new search tracks.

V1 is a regression baseline, not a gold standard. Its flattened metadata matching includes false positives such as phage samples that mention the bacterial host only in propagation metadata.

## Current confirmed result

- 533 confirmed BioSample pairs/unique accessions;
- 360 NCPPB strains with at least one confirmed BioSample;
- 307 strains with a selected Assembly;
- 50 strains with WGS SRA fallback data;
- 3 confirmed BioSamples with metadata only;
- 83 strains in the manual review queue, including provisional identities and accepted identities with taxonomy questions.

## BioProject correction

BioSample ELink returns generic annotation and umbrella projects. V2.1 classifies project mappings and includes only Assembly/SRA-derived sequence-source projects in the supervisor table. Annotation and ELink-only projects remain available in `bioproject_mapping.tsv` for audit.

## Reproducibility checks

The current code passes 69 automated tests. It has also passed:

1. a complete project-specific offline-cache replay with V1 regression inputs; and
2. a complete open-source-style replay from HTML without V1 inputs or HTML hash recording.

Both modes produce a valid one-row-per-current-strain supervisor table and the required intermediate evidence files.
