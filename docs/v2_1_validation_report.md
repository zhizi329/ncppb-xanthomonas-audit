# V2.1.1 Safety-Gate Validation Report

## Conclusion

V2.1 completed a full NCBI run over 897 current catalogue records. V2.1.1 then re-evaluated all saved V2.1 candidates and linked records with the new taxonomy/pathovar safety gate and passed the strengthened validator. This regression verifies the decision and selection logic; it is not presented as a fresh remote NCBI harvest. The workflow does not claim absolute recall over every record that might exist in NCBI.

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

## Current identity and downstream-use result

- 533 confirmed BioSample pairs/unique accessions;
- 360 NCPPB strains with at least one confirmed BioSample;
- 262 strains with an automatically eligible selected Assembly;
- 46 strains with an automatically eligible WGS SRA fallback;
- 49 strains with linked sequence but no automatic selection pending taxonomy/pathovar review;
- 3 confirmed BioSamples with metadata only;
- 92 strains / 112 strain--BioSample pairs in the manual review queues;
- 232 potentially actionable disabled identifiers in `identifier_review_queue.tsv`;
- 884 current rows named within *Xanthomonas* and 13 catalogue rows currently reclassified outside the genus, all retained with explicit scope labels.

Context metadata are now surfaced for later iTOL/explorer annotation: 81 strains have BioSample host, geography, date and isolation source; 267 have a partial set; 549 have none in accepted BioSamples. Catalogue host/country are retained separately. Pathogenicity is deliberately marked `not_assessed_requires_external_or_phenotype_data` rather than inferred from a species or pathovar name.

The gate changes a real biological decision, not just a display field. For NCPPB 2217, two *Staphylococcus aureus* runs are now blocked and the *Xylophilus ampelinus* run ERR3330907 is selected. For NCPPB 2930, the *Sphingomonas* Assembly/SRA links remain visible but no sequence is selected automatically.

## BioProject correction

BioSample ELink returns generic annotation and umbrella projects. V2.1 classifies project mappings and includes only Assembly/SRA-derived sequence-source projects in the supervisor table. Annotation and ELink-only projects remain available in `bioproject_mapping.tsv` for audit.

## Reproducibility checks

The current code passes 76 automated tests. It has also passed:

1. a complete project-specific saved-evidence replay with V1 regression inputs and the taxonomy/pathovar gate; and
2. a complete open-source-style replay from HTML without V1 inputs or HTML hash recording.

Both modes produce a valid one-row-per-current-strain supervisor table and the required intermediate evidence files.
