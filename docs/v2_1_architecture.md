# NCPPB–NCBI Audit V2.1 Architecture

## Purpose

V2.1 converts a user-supplied NCPPB catalogue HTML file into an auditable, one-row-per-strain table of public BioSample, Assembly, SRA and sequence-source BioProject accessions. V1 is optional and is used only as a regression baseline.

## Two independent BioSample discovery tracks

### NCPPB-number track

The primary track combines:

1. broad `NCPPB[All Fields]` prefix harvests; and
2. one literal full-identifier query per catalogue strain.

Full forms such as `NCPPB 45`, `NCPPB45` and `NCPPB:45` are OR-combined. The workflow never constructs an independent `NCPPB AND 45` query. Literal per-strain queries use `[Text Word]` because `[All Fields]` automatic term mapping can expand some strain identifiers into organism queries.

### Other-references track

The HTML parser preserves `<br>` clause boundaries before classifying donor references, collection lists, isolation-source text and isolate-source text. Formal collection numbers are harvested by trusted collection prefix and then mapped locally using complete bounded identifiers. Medium-strength donor or isolate codes can retrieve candidates but cannot be accepted automatically.

## Evidence hierarchy

- `primary`: the NCPPB catalogue number;
- `strong`: a recognised formal culture-collection number;
- `medium`: a sufficiently specific donor or isolate code;
- `weak`: a short or ambiguous code excluded from automatic search;
- `not_searchable`: preserved person/source text.

Cross-strain identifier collisions are disabled and added to the parser review queue.

## Local identity validation

ESearch is used only for candidate retrieval. Identity decisions are made locally against structured BioSample fields:

- `strain`;
- `isolate`;
- `culture_collection`;
- `bio_material`;
- `sample_name`;
- `identity_aliases`;
- `identifiers`.

Formatting differences between letters and numbers are tolerated, for example `XCP3` versus `Xcp-3`, while complete identifier boundaries are retained. A primary or strong identifier in a structured field is accepted unless a conflicting NCPPB number is present. Medium-code and title-only matches remain provisional.

Identity confirmation and taxonomy consistency are separate decisions. A strong identity match is retained when the NCBI organism name differs, but `taxonomy_review_required=yes` is recorded.

## Linked NCBI resources

Confirmed and provisional BioSamples are expanded through ELink and ESummary. Confirmed and provisional Assembly/SRA accessions remain in separate columns.

BioProject links receive additional provenance classification:

- `sequence_source_project`: recovered from Assembly GenBank metadata or SRA experiment metadata;
- `annotation_project`: a RefSeq annotation project;
- `biosample_elink_only`: returned only by BioSample ELink and not promoted automatically.

Only sequence-source projects appear in the confirmed supervisor BioProject column.

## Query execution controls

Every ESearch records its reported count, retrieved UID count, truncation state, warning count and error state. Trusted-prefix and full-NCPPB queries must complete without truncation. All remote responses are cached by semantic request parameters; credentials are excluded from cache keys.

## User HTML and optional provenance hash

`--catalogue-html` is required. The workflow accepts any compatible user-supplied catalogue file and does not compare it with a repository hash. HTML SHA-256 recording is off by default and is never an acceptance criterion. Researchers may opt in with `--record-input-hash` if their project requires an input fingerprint.

## Primary outputs

- `supervisor_sequence_availability.tsv`: one current NCPPB strain per row;
- `sequence_resource_manifest.tsv`: long-form resource and download-command table;
- `phylogeny_input_manifest.tsv`: one preferred sequence source per strain;
- `bioproject_mapping.tsv`: sequence, annotation and ELink-only project classification;
- `manual_review_queue.tsv`: unresolved identity or taxonomy cases.
