# Matching Decision Rules

This document records how candidate NCBI records should be judged.

## Evidence Levels

| Category | Meaning | Typical Evidence |
|---|---|---|
| `strong_strain_match` | The NCBI record likely refers to the same NCPPB strain. | NCPPB number appears in BioSample/Assembly/SRA metadata, or an equivalent collection number is present. |
| `probable_strain_match` | The record probably refers to the same strain, but evidence is incomplete. | Matching strain identifier plus compatible organism name/source metadata. |
| `taxon_level_only` | The record belongs to the same species/pathovar but does not prove strain identity. | Same organism name or TaxID only. |
| `ambiguous` | Candidate records exist but evidence conflicts or is too weak. | Different strain numbers, inconsistent metadata, or unclear synonyms. |
| `no_public_data_found` | No reliable BioSample/SRA/Assembly evidence was found. | No useful NCBI records after strain-level searching. |

## Matching Hierarchy

1. NCPPB catalogue number, e.g. `NCPPB 1234`.
2. Compact NCPPB number, e.g. `NCPPB1234`.
3. Equivalent collection numbers from other culture collections.
4. Strain identifier fields in BioSample metadata.
5. Current and historical taxonomic names.
6. Broader organism-level search.

## Tutor Feedback Reflected Here

The workflow should not simply check whether NCPPB and NCBI names are identical. It should disambiguate taxonomic names and preserve evidence for why a record was or was not accepted as a strain-level match.

NCBI TaxID should be recorded wherever available.
