# Sequence retrieval and phylogeny-input summary

- Current NCPPB strains: 897
- Preferred assembled genomes: 262
- WGS-read fallbacks: 46
- Selected BioProject provenance links: 308
- Long-form resource rows: 3009

## Readiness categories

- assembly_available_qc_required: 262
- confirmed_biosample_metadata_only: 3
- identity_review_required_before_use: 25
- no_confirmed_public_sequence: 512
- raw_wgs_reads_require_assembly_and_qc: 46
- taxonomy_review_required_before_use: 49

`BioSample` is the strain-identity anchor. `Assembly` and WGS `SRA` runs are sequence sources. BioProjects are used for provenance only when recovered from Assembly or SRA metadata; BioSample-only ELink projects are not automatically treated as sequence projects.
