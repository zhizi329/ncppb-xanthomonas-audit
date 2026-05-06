# Project Understanding

## Simple Explanation

The NCPPB keeps real bacterial strains. NCBI stores public genome-related records. This project checks whether each NCPPB Xanthomonas strain can be reliably connected to public NCBI records.

The output should help answer:

1. Does this NCPPB strain have public genome data?
2. Is the data complete genome, draft assembly, raw reads only, RNA-seq, or none?
3. Does the NCBI record clearly refer to the same strain, or only to the same taxon?
4. Are the NCPPB and NCBI names/taxonomic labels easy to reconcile?
5. Which strains or taxa should be prioritised for sequencing or catalogue review?

## Key Tutor Feedback Interpreted

- The project is useful and practical.
- Use NCBI TaxIDs as part of the workflow.
- Do not rely only on name consistency. The deeper task is taxonomic name disambiguation.
- Strong matching evidence should come from NCPPB catalogue numbers or equivalent strain/collection identifiers.
- Some strains may be held in multiple culture collections under different catalogue numbers.
- Some NCPPB catalogue records may already include links to sequence data. Keep these links in the master table.
- Treat incomplete metadata and inconsistent names as the project problem, not just as external risks.

## Working Definition

In this project, public genomic representation means:

> The level and reliability of public NCBI genome-related metadata that can be linked to a specific NCPPB strain.

This includes BioSample, SRA, Assembly, and Taxonomy records.
