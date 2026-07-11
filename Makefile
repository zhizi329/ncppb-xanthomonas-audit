PYTHON ?= python3
EMAIL ?= test@example.com
AUDIT_RUN ?= runs/audit/2026-07-10_v2.1.1
AUDIT_WORK ?= runs/audit/work
CATALOGUE_HTML ?= private_inputs/National Collection of Plant Pathogenic Bacteria Catalogue.html

.PHONY: test hygiene validate validate-reviewed dry-run audit-work

test:
	$(PYTHON) -B -m unittest

hygiene:
	$(PYTHON) -B scripts/check_repository_hygiene.py

validate:
	$(PYTHON) -B scripts/validate_ncppb_audit_v2.py \
		--outdir $(AUDIT_RUN) \
		--expected-current-records 897 \
		--expected-missing-number "NCPPB 4416"

validate-reviewed:
	$(PYTHON) -B scripts/validate_ncppb_audit_v2.py \
		--outdir $(AUDIT_RUN) \
		--expected-current-records 897 \
		--expected-missing-number "NCPPB 4416" \
		--require-reviewed

dry-run:
	$(PYTHON) -B scripts/run_ncppb_audit_v2.py \
		--catalogue-html "$(CATALOGUE_HTML)" \
		--outdir $(AUDIT_WORK)

audit-work:
	$(PYTHON) -B scripts/run_ncppb_audit_v2.py \
		--catalogue-html "$(CATALOGUE_HTML)" \
		--outdir $(AUDIT_WORK) \
		--run-ncbi \
		--email $(EMAIL)
