# Assisted Manual Review And `[All Fields]` Rejected-Result Analysis

本文档记录两件事：

1. 对 898-strain 审查表中 40 个 `manual_review_required` strains 的辅助人工审核建议。
2. 对旧 BioSample `[All Fields]` 检索结果的 rejected-result 数据分析，以及是否应改成 `[BioSample]` 字段。

当前不做新的 NCBI live rerun，也不扩展 Assembly/SRA/BioProject。

## 1. 辅助人工审核输出

生成命令：

```bash
python3 scripts/18_assist_manual_biosample_review.py \
  --review-table results/refactored_pipeline/07_search_result_review_898.tsv \
  --output results/refactored_pipeline/08_assisted_manual_biosample_review.tsv
```

输出文件：

```text
results/refactored_pipeline/08_assisted_manual_biosample_review.tsv
```

该表只给出辅助判断，不改写原始 accepted/rejected tables。

## 2. 40 个待审 strain 的当前辅助判断

| 辅助判断 | strains | 解释 |
|---|---:|---|
| `keep_confirmed_match_review_side_hits` | 15 | 已有 accepted BioSample；待审 accession 是 broad search side hit，不推翻 confirmed has-call。 |
| `no_confirmed_match_reject_conflicting_candidates` | 18 | 没有 accepted BioSample；候选记录指向其他 NCPPB number，不应计为本 strain。 |
| `no_confirmed_match_review_taxon_or_rescue` | 4 | 只有 target-taxon/query-only 或 rescue 候选；当前没有 exact strain evidence。 |
| `curator_check_accepted_conflict` | 3 | 当前 accepted BioSample 自身被 raw audit 标出 conflict，必须人工确认后才能最终计入。 |

推荐解释：

- 对 `keep_confirmed_match_review_side_hits`：本项目的“有无”表可暂时保留为 `confirmed_biosample_match`，但仍保留 side-hit accession 供导师检查。
- 对 `no_confirmed_match_reject_conflicting_candidates`：当前应归入 `no_confirmed_match_yet`，因为候选记录更支持其他 NCPPB strain。
- 对 `no_confirmed_match_review_taxon_or_rescue`：当前应写作 `no confirmed BioSample yet; possible false-negative/manual review candidate`。
- 对 `curator_check_accepted_conflict`：不能自动算 confirmed，也不能自动删除，必须人工看具体 BioSample metadata。

## 3. `[All Fields]` rejected-result 分析输出

生成命令：

```bash
python3 scripts/19_analyze_rejected_all_fields_keywords.py \
  --raw-audit analysis_tmp/biosample_raw_audit/raw_candidate_audit.tsv \
  --keyword-summary analysis_tmp/biosample_raw_audit/keyword_audit_summary.tsv \
  --prefix-recommendations analysis_tmp/biosample_raw_audit/prefix_keyword_recommendations.tsv \
  --output-dir analysis_tmp/all_fields_keyword_analysis
```

输出文件：

```text
analysis_tmp/all_fields_keyword_analysis/all_fields_overview.tsv
analysis_tmp/all_fields_keyword_analysis/all_fields_prefix_analysis.tsv
analysis_tmp/all_fields_keyword_analysis/all_fields_query_analysis.tsv
```

## 4. `[All Fields]` 的核心问题

当前旧 raw BioSample rows 全部来自 `[All Fields]` profile：

| 指标 | 数值 |
|---|---:|
| all-fields raw rows | 33,829 |
| prior accepted rows | 612 |
| clear noise rows | 31,673 |
| query no-hit rows | 1,242 |
| supports review rows | 305 |
| non-target organism rows | 31,827 |
| target organism rows | 760 |
| query-terms-present-separately rows | 30,707 |

这说明 `[All Fields]` 的主要问题是：短 prefix 和数字在记录任意位置分散出现，导致大量 query terms 共现，但没有形成 exact strain identifier。

例如：

| prefix/rule | raw rows | accepted | non-target | 建议 |
|---|---:|---:|---:|---|
| `B` / single-letter source code | 9,862 | 2 | 9,847 | fallback only |
| `X` / single-letter source code | 1,701 | 0 | 1,701 | disable default |
| `S` / single-letter source code | 1,108 | 0 | 1,108 | disable default |
| `PATEL` / person/local code | 1,086 | 4 | 1,082 | fallback only |
| `XP` / contextual code | 810 | 0 | 810 | disable default |
| `XC` / contextual code | 606 | 6 | 592 | fallback only |

## 5. 是否应该把 `[All Fields]` 改成 `[BioSample]`？

结论：**不建议简单改成 `[BioSample]`。**

原因：

- 目前我们已经在 BioSample database 中搜索；BioSample 是数据库上下文，不是解决短编码噪声的通用字段限制。
- NCBI EInfo for `db=biosample` 显示 BioSample 数据库可用字段包括 `All Fields`、`Accession`、`Title`、`Text Word`、`Organism`、`Attribute Name`、`Attribute`、`Submitter Organization` 等；没有一个适合把所有 strain 编号统一写成 `[BioSample]` 后替代 `[All Fields]` 的通用字段。
- 对 strain/culture collection identifier，实际更合理的是先用本地 curated identifier table 控制哪些 identifier 能检索，再用更窄字段做 pilot。

推荐替代策略：

1. 对 NCPPB number 和 high-confidence known collection identifiers：

```text
(NCPPB[Text Word] AND 45[Text Word]) AND Xanthomonas[Organism]
(ICMP[Text Word] AND 204[Text Word]) AND Xanthomonas[Organism]
```

2. 对 known collection identifiers 做 pilot 对照：

```text
(ICMP[Attribute] AND 204[Attribute]) AND Xanthomonas[Organism]
```

3. 对 noisy short/local/person codes：

```text
不要默认检索；只放 fallback/manual review。
```

4. 对 BioSample accession 本身，如 `SAMN...` / `SAMEA...`：

```text
使用 Accession 字段或直接 accession lookup，而不是文本关键词检索。
```

## 6. 下一步

当前最合理顺序：

1. 人工检查 `08_assisted_manual_biosample_review.tsv` 中 3 条 `curator_check_accepted_conflict`。
2. 把 15 条 `keep_confirmed_match_review_side_hits` 作为 confirmed but side-hit-noted。
3. 把 18 条 `no_confirmed_match_reject_conflicting_candidates` 暂列 no confirmed match。
4. 把 4 条 taxon/rescue candidates 留作 false-negative review。
5. 之后再回到关键词优化：基于 curated other-reference number table 生成 strict/fallback query plan。
