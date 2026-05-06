# Week 1 Plan: Environment and NCPPB Master Table

## Main Goal

Build the basic Linux project environment and create a clean NCPPB Xanthomonas master table.

## Why This Matters

Everything later depends on the quality of the starting strain list. If NCPPB numbers, names, pathovars, and alternative collection numbers are messy, NCBI matching will produce false positives.

## Tasks

1. Confirm WSL UbuntuBio works.
2. Create the project directory.
3. Set up Python virtual environment.
4. Install required Python packages.
5. Save or export the NCPPB Xanthomonas catalogue page into `data/raw/`.
6. Convert the raw NCPPB data into a master CSV.
7. Write down the meaning of each master-table column.

## Target Outputs

```text
README.md
requirements.txt
docs/wsl_quickstart.md
docs/project_understanding.md
docs/data_dictionary.md
data/raw/ncppbresult.html or data/raw/ncppb_catalogue.csv
data/processed/ncppb_xanthomonas_master.csv
```

## Success Criteria

By the end of Week 1, you should be able to explain:

- where the project is stored;
- how to activate the Python environment;
- what each row in the NCPPB master table represents;
- why strain numbers are more important than species names for matching.
