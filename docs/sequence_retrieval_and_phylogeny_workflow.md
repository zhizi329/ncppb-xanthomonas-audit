# Sequence Retrieval and Phylogeny-Input Workflow

## Database roles

| Database | Role | Direct phylogeny input |
|---|---|---|
| BioSample | Strain-identity anchor | No |
| Assembly | Assembled genome and assembly metadata | Yes, after QC |
| SRA | Raw sequencing reads | After read QC, assembly and assembly QC |
| BioProject | Project provenance | No |

BioProject is not accepted merely because BioSample ELink returns it. Sequence provenance is assigned only when a project is embedded in Assembly GenBank metadata or SRA experiment metadata. RefSeq annotation and ELink-only projects remain visible in the audit table but are not promoted into the supervisor result.

## Download tools

Assembly FASTA files use NCBI Datasets CLI commands generated in `sequence_resource_manifest.tsv`:

```bash
datasets download genome accession GCF_020783895.1 \
  --include genome \
  --filename NCPPB_101_GCF_020783895.1.zip
```

Raw reads use NCBI SRA Toolkit commands:

```bash
prefetch SRR22272561
fasterq-dump SRR22272561 --split-files --outdir fastq/NCPPB_101
```

Only confirmed SRA records with `LIBRARY_STRATEGY=WGS` and `LIBRARY_SOURCE=GENOMIC` (or an empty source value) are eligible as phylogeny fallbacks.

## One preferred sequence source per strain

Selection order:

1. highest assembly level: Complete Genome, Chromosome, Scaffold, then Contig;
2. RefSeq (`GCF_`) before GenBank (`GCA_`) within the same level;
3. higher contig N50 as the next tie-breaker;
4. if no confirmed Assembly exists, choose the confirmed WGS BioSample with the most reported bases and retain all of its runs;
5. never select a provisional-only identity automatically.

Every selected resource remains `qc_required=yes`. Identity confidence does not establish sequence quality.

## Current V2.1 readiness

- 897 current catalogue strains;
- 307 preferred assembled genomes;
- 50 WGS-read fallbacks requiring assembly;
- 3 confirmed BioSamples with metadata only;
- 25 provisional-only strains requiring identity review;
- 512 strains with no confirmed public sequence.

The current theoretical QC input is therefore 357 strains, not 357 immediately tree-ready genomes.

## Next analysis boundary

Before tree construction:

1. verify accession versions and download integrity;
2. apply consistent raw-read QC and assembly to the 50 SRA-only strains;
3. assess genome length, contig count, N50, completeness and contamination;
4. remove duplicate samples/strains;
5. decide whether the biological question requires a genus-wide marker/core-genome tree or species/pathovar-specific core-SNP analyses;
6. record software versions, parameters, input filenames/dates and exclusion reasons.

The current machine does not have `datasets`, `prefetch` or `fasterq-dump` installed. Generated commands are an auditable acquisition plan, not evidence that sequence files have already been downloaded.
