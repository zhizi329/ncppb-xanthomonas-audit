# NCPPB 审计工作流框架设计

本文档描述当前 NCPPB Xanthomonas genome audit 项目的主线框架、已完成程度、下一步拆分，以及为何需要先分析 rejected result 再调整 NCBI 检索参数。它面向人工审阅和后续脚本扩展；在人工审阅前，不应上传 GitHub、push、开 PR 或把结果当作最终审计表发布。

## 1. 当前完成程度

当前仓库已经完成了一个可运行的 BioSample identifier workflow，但还没有完成最终 collection-wide audit。

已完成的部分：

- NCPPB Xanthomonas master table 已从浏览器保存的 NCPPB catalogue HTML/CSV 中整理出来，当前为 898 条 strain 记录。
- `Other references` 已被抽取，并转换为 identifier candidate 表。
- 旧版全量 BioSample harvest 已运行，产生 33,829 条 raw candidate rows。
- 严格本地过滤已从 raw candidates 中接受 612 条 BioSample rows，覆盖 370 个 NCPPB strains。
- BioSample 到 SRA、BioProject、BioCollections 的 linked-record expansion 已有初版脚本，但尚未整合成最终 one-row-per-strain audit。

尚未完成的部分：

- rejected/review result 还没有可复现的数据分析脚本。
- 检索参数仍受旧策略影响，尤其是短 identifier 使用 `[All Fields]` 后产生大量非 Xanthomonas hits。
- 还没有稳定的 final strain audit table，将 BioSample、SRA、Assembly/BioProject、manual-review flags 合并到一行。
- 全 NCPPB 数据库扩展还需要 organism filter、缓存、断点续跑和批处理策略。

## 2. 模块拆分

建议把项目拆成以下可独立审阅的模块。

1. NCPPB catalogue import
   - 输入：浏览器保存的 `data/raw/ncppbresult.html` 或手工导出的 catalogue CSV。
   - 主脚本：`scripts/00_extract_ncppb_html.py`、`scripts/01_clean_ncppb_catalogue.py`。
   - 原因：NCPPB catalogue 可能依赖浏览器 session，直接脚本下载可能出现 403；所以保存的 HTML/CSV 应作为可追溯 source of truth。

2. Identifier extraction
   - 输入：NCPPB `Other references`。
   - 主脚本：`scripts/08_html_to_other_references.py`、`scripts/09_extract_other_reference_identifiers.py`。
   - 策略：保留所有候选 identifier 作为 evidence，但默认只搜索高/中可信 identifier。低可信 single-letter、本地 donor/person code 默认不进 NCBI search。

3. NCBI query generation and BioSample harvest
   - 主脚本：`scripts/10_harvest_biosample_raw.py`。
   - 默认 profile：`strict_xanthomonas`，使用 `[Text Word]` terms 加 `Xanthomonas[Organism]`。
   - 复现 profile：`current_all_fields`，只用于解释旧结果。
   - 扩展 profile：`known_collection_strict` 用于高可信 culture collection prefixes；`broad_review` 用于 false-negative 排查，不直接作为最终 accepted 证据。

4. Rejected-result diagnostics
   - 主脚本：`scripts/14_analyze_biosample_rejections.py`。
   - 输出：reject reason、prefix、search term、strain-level summary、manual-review priority tables。
   - 用途：先量化噪声来源，再决定哪些 prefix/rule/query profile 应保留、降级或禁用。

5. Match classification
   - 主脚本：`scripts/11_filter_biosample_raw.py`。
   - 原则：NCBI hit 只代表候选；最终 accepted match 必须由本地 metadata 中的 exact NCPPB number 或高可信 equivalent collection identifier 支持。

6. Linked-record expansion
   - 主脚本：`scripts/13_link_biosample_related_records.py`。
   - 目标：从 accepted BioSample 出发扩展 SRA、BioProject、BioCollections 等 linked records，避免直接用 broad sequence database search 造成 strain identity 混淆。

7. Final strain audit
   - 目标输出：one-row-per-strain audit table。
   - 应包含：best audit category、accepted BioSample accessions、linked SRA/BioProject/Assembly evidence、taxon consistency notes、manual review flags、query profile/version。

## 3. NCBI 检索策略

导师指出 rejected result 应用于优化检索参数，这是当前最重要的下一步。旧策略的问题是把 identifier 拆成多个 `[All Fields]` term，例如 `B[All Fields] AND 67[All Fields]`。这会命中大量 human、metagenome、mouse、environmental sample 等无关 BioSample。

新的默认策略：

- `strict_xanthomonas`：`PREFIX[Text Word] AND NUMBER[Text Word] AND Xanthomonas[Organism]`。
- `known_collection_strict`：只搜索 `known_collection_prefix` 且 high confidence 的 identifiers，例如 `NCPPB`、`CFBP`、`ICMP`、`LMG`、`ATCC`。
- `current_all_fields`：保留旧 `[All Fields]` 逻辑，仅用于复现和比较。
- `broad_review`：不加 organism filter 的 `[Text Word]` search，仅用于排查疑似 false negatives。

注意：即使 query profile 变严格，accepted match 仍必须经过本地 filtering。检索参数只控制 candidate recall/precision，不直接决定 strain-level match。

## 4. Rejected Result 分析输出

`script 14` 应作为导师要求的 rejected result data analysis。建议输出目录放在 `analysis_tmp/biosample_rejection_diagnostics/` 或正式结果目录下的一个 dated folder。

关键输出：

- `rejection_counts_by_reason.tsv`：确认 rejected result 的主要来源。
- `prefix_noise_summary.tsv`：定位高噪声 prefixes，如 `B`、`X`、`XP`、`S`、`XC`。
- `search_term_productivity.tsv`：比较每个 query 的 accepted rows、review rows、non-Xanthomonas rows、taxon-only rows。
- `strain_rejection_summary.tsv`：查看每个 NCPPB strain 的 rejected burden。
- `manual_review_priority_candidates.tsv`：优先检查 `taxon_level_only` 和 conflicting NCPPB number。

这些表应先用于人工审阅，再决定是否全量重跑 NCBI。

## 5. 全 NCPPB 数据库扩展

当前项目仍以 Xanthomonas 为 case study。若将来扩展到整个 NCPPB database，不能把 `Xanthomonas[Organism]` 写死在规则里。应改为：

- 每个 batch 设置一个 `--target-organism`，例如 genus-level 或 curator-approved taxon group。
- 对 genus 混杂或 taxonomy uncertain 的 batch，先跑 high-confidence collection identifiers，再人工审阅 broad fallback。
- 使用 `--cache-dir` 缓存 ESearch/ESummary JSON，降低重复请求。
- 使用 `--resume` 断点续跑，避免长任务中断后从头开始。
- 每次 rerun 都记录 query profile、target organism、run date、NCBI API 参数和 script version。

## 6. 推荐执行顺序

1. 运行 rejected result analysis，生成诊断表。
2. 人工审阅 top noisy prefixes、taxon-only candidates 和 conflicting NCPPB number candidates。
3. 用小 pilot set 比较 `current_all_fields`、`strict_xanthomonas`、`known_collection_strict`。
4. 确认 accepted matches 没有明显流失后，再对 898 条 Xanthomonas strains 重跑 BioSample harvest。
5. 通过 `script 11` 重新过滤，再用 `script 13` 扩展 linked records。
6. 生成 final strain-level audit table。

## 7. 外部依据

- NCBI BioSample Advanced Search 支持 `Organism`、`Text Word`、`Title`、`Attribute`、`Attribute Name` 等字段：https://www.ncbi.nlm.nih.gov/biosample/advanced
- BioSample metadata 使用结构化 attribute name/value 描述样本，包括 strain/isolate 相关字段：https://www.ncbi.nlm.nih.gov/biosample/docs/attributes/
- NCPPB catalogue 是在线 collection catalogue，项目应保留网页保存结果作为 source evidence：https://www.ukbrcn.org/who-we-are/national-collection-of-plant-pathogenic-bacteria-ncppb/
