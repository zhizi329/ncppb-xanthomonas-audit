# 最小仓库结构

Git 只保存当前代码、测试、简明文档、897 株权威审计 run，以及 smoke test 的 accession/QC/最终树摘要。

FASTQ、BAM、SRA cache、软件环境、Excel 预览、旧版结果、重复中间表和可重建工作目录不保存。

| 目录 | 内容 |
|---|---|
| `ncppb_audit_v2/` | V2.1.1 审计库 |
| `scripts/` | 当前 CLI、验证和三物种 smoke-test 工具 |
| `tests/` | 当前 V2.1 测试 |
| `data/` | 小型 898 株历史 baseline 表 |
| `runs/audit/` | 当前 897 株权威审计运行 |
| `runs/phylogeny/` | accession、QC、距离和树摘要 |
| `docs/` | 当前方法、字段和人工审核说明 |
| `private_inputs/` | 本地 proposal 与 NCPPB HTML；不进入 Git |
| `work` | 指向仓库外 `../xanthomonas-data/` 的本地软链接；不进入 Git |

不再创建 `results/`、`outputs/`、`archive/`、`deliverables/`、`local_data/` 或 `scratch/`。需要继续分析的大型数据统一放在 `work/`，而不是删除或提交到 Git。

只从以下文件引用 headline counts：

1. `supervisor_sequence_availability.tsv`；
2. `phylogeny_input_manifest.tsv`；
3. `manual_review_queue.tsv`；
4. `run_summary.md`；
5. `run_manifest.json`。

仓库维持单一 `main` 分支。提交前运行 `make hygiene test validate`。大型生物数据只保存 accession、MD5、QC summary 和排除理由。

`environment.yml` 是构树软件环境的唯一版本化定义；实际环境创建在被忽略的
`.cache/conda-envs/phylogeny/`。FASTQ、BAM、reference 和中间结果物理保存在仓库外的
`../xanthomonas-data/`，仓库内的 `work` 只是被忽略的软链接。这样重建或清理 Git
工作树不会再次删除测序数据。
