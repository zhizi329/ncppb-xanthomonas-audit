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
3. Equivalent collection numbers from other culture collections, including identifiers found in NCPPB `Other references`.
4. Strain identifier fields in BioSample metadata.
5. Current and historical taxonomic names.
6. Broader organism-level search.

## Harvest Query Rules

BioSample searching should be driven by strain identifiers, not by catalogue names, host, geography, or broad taxonomic labels.

The old `current_all_fields` profile is retained only for reproducibility. It used broad terms such as `NCPPB[All Fields] AND 45[All Fields]`, which maximised recall but produced many rejected non-target records.

The current default direction is a strict fielded profile:

```text
(NCPPB[Text Word] AND 45[Text Word]) AND Xanthomonas[Organism]
```

Trusted equivalent collection identifiers should use the same pattern, for example:

```text
(ICMP[Text Word] AND 204[Text Word]) AND Xanthomonas[Organism]
```

Low-confidence local, source, donor, or person-associated codes should be retained as review evidence but should not enter the default search plan. They may be used in a separate fallback/rescue plan, where results require manual review before acceptance.

The search identifiers are limited to the NCPPB number and numbering-style identifiers extracted from `Other references`. Exact matching is still handled after retrieval by local metadata filtering.

## Linked Record Sets

When one BioSample is accepted by exact NCPPB number or equivalent collection number, Assembly and SRA records linked to the same BioSample can be grouped into the same accepted record set. This link is recorded as `linked_accepted_biosample`.

Records with a conflicting NCPPB number or a non-Xanthomonas organism label are not promoted by BioSample linkage and remain review candidates.

## Rejected-Result Policy

Rejected-result analysis should feed back into query generation:

1. keep NCPPB numbers and high-confidence culture collection prefixes in strict default search;
2. move noisy short prefixes such as single-letter local codes to fallback or manual review;
3. do not treat a query hit as proof of strain identity;
4. require exact local metadata evidence before accepting a BioSample;
5. preserve no-hit and target-taxon-only rows for audit coverage and possible false-negative review.

## Tutor Feedback Reflected Here

The workflow should not simply check whether NCPPB and NCBI names are identical. It should disambiguate taxonomic names and preserve evidence for why a record was or was not accepted as a strain-level match.

NCBI TaxID should be recorded wherever available.
