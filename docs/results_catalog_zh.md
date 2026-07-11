# 结果文件目录

## 权威入口

路径：`runs/audit/2026-07-10_v2.1.1/`

| 优先级 | 文件 | 用途 |
|---:|---|---|
| 1 | `supervisor_sequence_availability.tsv` | 897 株序列可用性与审核状态 |
| 2 | `phylogeny_input_manifest.tsv` | 每株首选 Assembly/WGS 与阻断原因 |
| 3 | `manual_review_queue.tsv` | 92 株人工审核任务 |
| 4 | `run_summary.md` | 当前运行统计 |
| 5 | `run_manifest.json` | 版本、时间、参数和文件校验和 |

## 支撑证据

| 文件 | 粒度 |
|---|---|
| `biosample_candidates.tsv` | NCBI candidate；命中不等于接受 |
| `biosample_match_decisions.tsv` | strain-BioSample pair |
| `linked_ncbi_records.tsv` | Assembly/SRA/BioProject record |
| `sequence_resource_manifest.tsv` | 下载与 provenance resource |
| `ncbi_query_plan.tsv` / `ncbi_query_execution.tsv` | 查询计划与执行审计 |
| `v1_regression_recall_audit.tsv` | 历史配对回归控制 |
| `identifier_review_queue.tsv` / `parser_review_queue.tsv` | 标识符与解析审核 |

## 发育树 smoke test

`runs/phylogeny/2026-07-10_three-species-snp-smoke-summary/` 只保留 accession、ENA MD5、QC、SNP 距离、*X. citri* IQ-TREE 和 iTOL 文件。
