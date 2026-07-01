# Draft progress update for David / Teams

Hi David,

I have now completed a revised V2.1 run of the core NCPPB–NCBI matching workflow.

The main supervisor-facing table is:

`results/v2_1_pipeline/supervisor_sequence_availability.tsv`

It contains one row for each of the 897 Xanthomonas-related records in the current NCPPB catalogue snapshot and reports confirmed BioSample, Assembly, SRA and sequence-source BioProject accessions. The current results include 533 confirmed BioSamples covering 360 NCPPB strains. Of these, 307 strains have an assembled genome and another 50 have confirmed WGS reads that could be assembled. Three confirmed BioSamples currently have metadata only.

I have also added two reproducible data-acquisition tables:

- `results/v2_1_pipeline/sequence_resource_manifest.tsv`: a long-form list of BioSample, Assembly, SRA and BioProject resources, including the recommended NCBI download tool and command;
- `results/v2_1_pipeline/phylogeny_input_manifest.tsv`: one row per NCPPB strain, selecting the preferred assembly or WGS-read source for later genome QC and phylogenetic analysis.

BioProject links are now filtered more carefully. Only projects recovered from Assembly or SRA metadata are treated as sequence provenance; generic RefSeq annotation projects and BioSample-only ELink projects remain in a separate audit table and are not presented as the strain's sequencing project.

The complete run used 1,376 audited NCBI queries with no truncation or request/link errors. As a regression check, all 516 historical V1 strain–BioSample pairs that still satisfy the V2.1 confirmation criteria were rediscovered by the new search tracks.

The next stage would be to download the 307 selected assemblies and the WGS reads for the remaining 50 strains, apply consistent genome QC/assembly criteria, and then decide whether the phylogenetic analysis should be genus-wide or stratified by species/pathovar.

I would be very grateful for any comments on the main table, particularly any strain links or sequence-availability categories that you think should be revised.

Best wishes,

Xiao
