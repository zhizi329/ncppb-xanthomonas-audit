# How To Bring The NCPPB Browser Data Into The Project

The NCPPB result page may depend on your browser session, so direct scripted download can fail with `403 Forbidden`.

Use one of these methods.

## Option A: Save Page HTML

1. In the browser tab showing the Xanthomonas NCPPB results, press `Ctrl+S`.
2. Save the page as HTML.
3. Put the file here:

```text
/home/zhizi/projects/ncppb-xanthomonas-audit/data/raw/ncppbresult.html
```

From Windows Downloads, the WSL path is usually:

```text
/mnt/c/Users/0329z/Downloads/<filename>.html
```

## Option B: Copy Table To CSV

If the page table can be selected:

1. Select the result table in the browser.
2. Copy it into Excel.
3. Save as CSV.
4. Put the file here:

```text
/home/zhizi/projects/ncppb-xanthomonas-audit/data/raw/ncppb_catalogue.csv
```

## After Saving

Run:

```bash
cd /home/zhizi/projects/ncppb-xanthomonas-audit
source .venv/bin/activate
python scripts/01_clean_ncppb_catalogue.py --input data/raw/ncppb_catalogue.csv --output data/processed/ncppb_xanthomonas_master.csv
```

If you saved HTML, we will add an HTML extraction step once we inspect the exact table structure.


## Copy From Windows Downloads Into WSL

If you save the page to Windows Downloads, copy it into the project with:

```bash
cp /mnt/c/Users/0329z/Downloads/ncppbresult.html   /home/zhizi/projects/ncppb-xanthomonas-audit/data/raw/ncppbresult.html
```

Then extract the table:

```bash
cd /home/zhizi/projects/ncppb-xanthomonas-audit
source .venv/bin/activate
python scripts/00_extract_ncppb_html.py   --input data/raw/ncppbresult.html   --output data/raw/ncppb_catalogue.csv
```
