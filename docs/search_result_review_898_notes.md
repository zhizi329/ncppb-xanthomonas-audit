# 898-strain BioSample 检索结果审查表说明

当前目标是先回答每个 NCPPB Xanthomonas strain 在现有 BioSample workflow 中“有无 confirmed match / 是否需要人工复核”，关键词优化和新一轮 NCBI 检索放到后面。

生成脚本：

```bash
python3 scripts/17_build_search_result_review_table.py \
  --master data/processed/ncppb_xanthomonas_master.csv \
  --identifiers results/refactored_pipeline/02_other_reference_identifiers.tsv \
  --matches results/refactored_pipeline/04_biosample_matches_all.tsv \
  --review results/refactored_pipeline/04_biosample_review_all.tsv \
  --raw-audit analysis_tmp/biosample_raw_audit/raw_candidate_audit.tsv \
  --rescue-candidates analysis_tmp/biosample_raw_audit/false_negative_rescue_candidates.tsv \
  --output results/refactored_pipeline/07_search_result_review_898.tsv
```

## 输出文件

`results/refactored_pipeline/07_search_result_review_898.tsv`

该表一行一个 NCPPB strain，共 898 行。核心列：

- `has_confirmed_biosample`：当前 algorithmic filter 是否已有 accepted BioSample。
- `search_result_review_status`：给导师看的当前审查状态。
- `review_priority`：如果需要人工复核，说明复核优先级。
- `accepted_biosample_accessions`：当前 accepted BioSample accessions。
- `conflict_rows` / `taxon_only_rows` / `rescue_candidate_count`：为什么不能简单判定为 confirmed 或 no data。
- `identifier_candidates` / `current_search_identifiers` / `manual_only_identifiers`：保留 Other references 编码背景，但本表不做最终关键词优化。

## 当前统计

基于现有本地结果：

| 状态 | strains |
|---|---:|
| `confirmed_biosample_match` | 352 |
| `manual_review_required` | 40 |
| `no_confirmed_match_yet` | 506 |

补充解释：

- `has_confirmed_biosample=yes` 的 strains：370。
- 其中 352 个没有当前高优先级复核标记，因此状态是 `confirmed_biosample_match`。
- 另有 18 个虽然已有 accepted BioSample，但同时存在 conflict/taxon-only/rescue 线索，因此状态是 `manual_review_required`。
- `has_confirmed_biosample=no` 的 strains：528，其中 22 个因为 conflict/taxon-only/rescue 线索需要复核，506 个当前没有 confirmed BioSample match。
- accepted BioSample rows 总数仍是 612。

## 状态规则

`manual_review_required` 优先级最高。只要存在以下情况之一，就进入人工复核：

1. 当前 accepted BioSample 在 raw audit 中出现 conflicting NCPPB number 或其他 audit warning。
2. review/rejected rows 中存在 conflicting NCPPB number。
3. 存在 target-taxon BioSample candidate，但没有 exact strain identifier。
4. raw audit 标记为 false-negative rescue candidate。

如果没有人工复核标记且有 accepted BioSample，则为：

```text
confirmed_biosample_match
```

如果没有人工复核标记且没有 accepted BioSample，则为：

```text
no_confirmed_match_yet
```

## 本周提交时的表述

这张表不是最终 genome availability table，也不尝试判断 complete genome / draft assembly / reads-only。它只回答当前 BioSample 检索与筛选结果中的“有无”和“是否需要复核”：

- 有 confirmed BioSample：当前可追溯到 accepted local identifier evidence。
- 无 confirmed BioSample：当前本地证据不足，不能确认公共 BioSample。
- 待复核：存在 conflict、taxon-only 或 rescue 线索，不能简单归入 confirmed 或 no data。

关键词优化、新 strict query plan、Assembly/SRA/BioProject 扩展都应在该表人工审阅后再继续。
