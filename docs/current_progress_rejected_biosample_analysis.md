# 当前进度：898 strains 审查表与 rejected BioSample 分析

更新日期：2026-06-01

## 目前已经完成的核心产物

1. `results/refactored_pipeline/07_search_result_review_898.tsv`
   - 898 个 NCPPB Xanthomonas strains 全覆盖。
   - 当前审查状态：
     - `confirmed_biosample_match`: 352 strains
     - `manual_review_required`: 40 strains
     - `no_confirmed_match_yet`: 506 strains
   - 已确认 BioSample 匹配：612 accepted BioSample rows，覆盖 370 strains。

2. `results/refactored_pipeline/08_assisted_manual_biosample_review.tsv`
   - 对 40 个 `manual_review_required` strains 做了辅助人工审核分层。
   - 15 个是已有 confirmed match 之外的 side hits，可保留 confirmed 结论。
   - 18 个暂无 confirmed match，主要是 conflicting candidates，应作为 rejected/manual review 证据。
   - 4 个暂无 confirmed match，需要继续检查 taxon-only 或 rescue candidates。
   - 3 个 accepted match 本身存在 conflicting NCPPB signal，需要 curator 重点核查：NCPPB 646、NCPPB 1607、NCPPB 1646。

3. `analysis_tmp/all_fields_keyword_analysis/`
   - 已按 prefix/rule/search term 分析旧 `[All Fields]` 检索的噪声。
   - 关键结论：短码和 local/person/source codes 是 false positive 的主要来源。

4. `results/refactored_pipeline/09_rejected_biosample_metadata_analysis/`
   - 本次新增的 rejected BioSample metadata-field 分析结果。
   - 这些表用于向导师说明 rejected rows 到底来自 BioSample 的哪些字段，以及为什么不能简单把 `[All Fields]` 改成 `[BioSample]`。

## 本次新增结果表

目录：`results/refactored_pipeline/09_rejected_biosample_metadata_analysis/`

- `rejected_biosample_metadata_overview.tsv`
  - 汇总 All Fields raw/rejected/accepted 总数和主要解释指标。
- `rejected_by_metadata_field.tsv`
  - 按 query term 在 BioSample metadata 中命中的字段统计，例如 `metadata_text`、`attributes`、`identifiers`、`title`、`infraspecies`、`organism`。
- `rejected_by_identifier_evidence.tsv`
  - 按 `keyword_match_class`、`raw_audit_decision`、`audit_reason`、`prior_reject_reason`、`organism_class` 解释 rejected rows。
- `rejected_by_biosample_attribute.tsv`
  - 解析 BioSample `attributes` 和 `infraspecies`，统计 `strain`、`isolate`、`culture_collection`、`host`、`collection_date` 等属性键。
- `search_script_modification_recommendations.tsv`
  - 根据本次 rejected-result 证据给出的检索脚本修改建议。
- `report_ready_rejected_analysis_summary.tsv`
  - 面向汇报的简短结果表，把关键数字、证据表和可直接表述的结论放在同一张表中。

## rejected-result 分析结论

旧 `[All Fields]` raw harvest 共 33,829 rows：

- accepted rows：612
- non-accepted rows：33,217
- non-target organism non-accepted rows：31,827
- target organism non-accepted rows：148
- query no-hit rows：1,242
- query terms present separately rows：30,707

这说明主要问题不是 BioSample 数据完全缺失，而是旧检索策略把 prefix 和 number 在记录中任意位置分别出现的情况也召回了。多数 rejected rows 不是 exact strain identifier match，而是 query terms 分散出现在 `metadata_text`、`attributes`、`title` 或 submitter/sample metadata 中。

字段层面上，rejected rows 中 query term 最常出现在：

- `metadata_text`: 31,975 rows
- `attributes`: 28,738 rows
- `identifiers`: 6,760 rows
- `title`: 6,665 rows
- `infraspecies`: 3,000 rows
- `organism`: 310 rows

BioSample attribute 层面，rejected rows 常见字段包括 `collection_date`、`geo_loc_name`、`isolation_source`、`sample name`、`Submitter Id`、`scientific_name`、`isolate`、`strain` 等。这些字段本身并不都等价于 strain identity，所以 query hit 不能直接作为匹配证据。

## 对 `[All Fields]` 与 `[BioSample]` 的判断

不建议把 `[All Fields]` 机械替换为 `[BioSample]`。

原因是 BioSample 是数据库名称，不是一个能精准限制 strain identifier 的通用字段。更合理的策略是在 BioSample 数据库内使用有明确语义的字段：

- `Text Word`：用于 `NCPPB`、`ICMP`、`LMG`、`ATCC` 等 trusted identifier 的 prefix 和 number。
- `Organism`：用于默认限制目标类群，例如 `Xanthomonas[Organism]`。
- `Attribute`：可作为 pilot profile 测试 known collection identifiers，但不应直接替代所有搜索。
- `Accession`：仅用于 SAMN/SAMEA/SAMD 等 BioSample accession。

当前最稳妥的默认检索形式仍是：

```text
(NCPPB[Text Word] AND 45[Text Word]) AND Xanthomonas[Organism]
```

对于 trusted other reference number，例如 `ICMP 204`、`LMG 673`：

```text
(ICMP[Text Word] AND 204[Text Word]) AND Xanthomonas[Organism]
(LMG[Text Word] AND 673[Text Word]) AND Xanthomonas[Organism]
```

## 检索脚本修改建议

1. `scripts/10_harvest_biosample_raw.py`
   - 保留 `current_all_fields` profile 只用于复现旧结果。
   - 下一轮 full rerun 默认使用 strict profile。
   - 默认 query 不应包含 `[All Fields]`。

2. `scripts/09_extract_other_reference_identifiers.py`
   - 继续提取所有 possible identifier candidates。
   - 但输出语义应区分：
     - `trusted_default_search`
     - `fallback_only`
     - `manual_review_only`
     - `reject_noise`
   - 短单字母 codes、person/source/local codes 不应进入 default search。

3. curated other-reference number table
   - 下一步最关键是把 Other references 编码表做成可信中间层。
   - NCPPB number 和 known collection prefix 是 default search 主体。
   - low-confidence local code 保留为 review evidence，不删除。

4. post-harvest filtering
   - 即使使用 strict query，也不能只因为 query hit 就接受。
   - accepted BioSample 必须有 local metadata 中的 exact NCPPB 或 trusted equivalent identifier。
   - conflicting NCPPB number 必须覆盖 query hit。

5. fallback/rescue
   - 对 local code 的检索应进入单独 fallback query plan。
   - fallback result 只能作为 rescue candidate，不直接进入 accepted table。

## 本周汇报可以这样概括

当前已经完成了 898 strains 的 BioSample 审查总表，并确认旧 `[All Fields]` 策略虽然保证召回，但带来了大量 non-Xanthomonas false positives。rejected-result 分析显示，主要噪声来自短码、local/person/source codes，以及 query terms 在 BioSample metadata 中分散出现而非形成 exact strain identifier。下一步不应简单改成 `[BioSample]`，而应采用 `Text Word + Organism` 的 strict profile，并把 Other references 编码表分层：trusted default search、fallback-only、manual review evidence、rejected noise。

## 暂不执行的内容

- 不重新联网跑 NCBI full harvest。
- 不扩展 Assembly/SRA/BioProject。
- 不做 GitHub commit、push、PR 或 upload。
- 等 898 审查表、manual review rows 和 rejected-result 分析经人工确认后，再生成下一轮 strict query plan。
