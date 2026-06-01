# BioSample raw data 审核脚本与关键词优化策略

本文档说明 `scripts/15_audit_biosample_raw_candidates.py` 的设计目的、代码逻辑、输出文件，以及如何用 rejected result 反向优化 NCBI BioSample 检索关键词。该脚本不上传 GitHub，不改变现有 raw/match/review 数据，只读取现有 TSV 并在 `analysis_tmp/biosample_raw_audit/` 生成审核表。

## 1. 为什么需要单独的 raw data audit

当前流程中已有两个关键脚本：

- `scripts/11_filter_biosample_raw.py`：把 raw BioSample rows 分为 accepted matches 和 review/rejected rows。
- `scripts/14_analyze_biosample_rejections.py`：统计 rejected rows 的数量、prefix 噪声和 search term productivity。

这两个脚本仍缺少一个中间解释层：某条 raw row 为什么会被检索出来？检索词到底出现在 NCBI 元数据哪个字段？它是本地 strain 证据、弱关键词共现，还是纯粹噪声？

`15_audit_biosample_raw_candidates.py` 的定位就是补这个中间层。它逐条审核 raw candidate，不直接替代 script 11 的最终分类，而是解释检索关键词质量，并把 rejected result 转换成下一轮 query policy 建议。

## 2. 核心原则

### 2.1 不把 query hit 当作 strain evidence

NCBI ESearch 只能说明某个 query term 在记录中出现，不能说明记录属于目标 NCPPB strain。脚本把证据分成三层：

1. **强证据：exact identifier pattern**
   - `NCPPB 45`、`NCPPB:45`、`NCPPB_45` 等可解释变体。
   - 高置信 collection identifiers，例如 `ICMP 204`、`LMG 673`、`CFBP ...`。
   - 只有 exact pattern 命中，才可视为 strain-level evidence。

2. **弱证据：query terms present separately**
   - 例如 `B[All Fields] AND 67[All Fields]` 的 `B` 和 `67` 都出现，但并没有形成 `B 67` 这样的 identifier pattern。
   - 这种证据只能进入 manual review，不能自动接受。

3. **噪声证据：non-target organism / prefix-only / suffix-only**
   - 如果 raw hit 是 `Homo sapiens`、`Ralstonia` 等非目标 organism，并且没有强 identifier，则标为 `clear_noise`。
   - 这类结果用于关闭或降级关键词。

### 2.2 低置信 Other references 不默认检索，但保留救援价值

短代码、单字母代码、本地 donor code、疑似人名编号不能作为默认检索词。它们应保留在 identifier table 中作为 review evidence。若这些低置信 identifiers 在 Xanthomonas raw metadata 中 exact match，则脚本标记为 `possible_false_negative_rescue`，用于小批量人工回查，而不是默认纳入全量检索。

### 2.3 默认策略必须远离 `[All Fields]`

旧 raw data 中大量假阳性来自 `[All Fields]`，尤其是 `B`、`X`、`XP`、`S`、`PATEL`、`XC`。脚本的推荐目标是把关键词分为：

- `keep_strict_profile`：保留，但必须用 `Text Word` + organism filter 等严格 profile。
- `keep_default`：在当前严格默认策略下可保留。
- `fallback_only`：只在 selected no-hit/lost strains 中使用。
- `manual_review_only`：仅作为人工复核线索。
- `disable_default`：默认检索关闭。
- `no_hit_evidence_only`：记录无命中事实，不作为扩展关键词。

## 3. 输入文件

典型命令：

```bash
python3 scripts/15_audit_biosample_raw_candidates.py \
  --raw-input results/refactored_pipeline/03_biosample_raw_all.tsv \
  --identifiers results/refactored_pipeline/02_other_reference_identifiers.tsv \
  --matches results/refactored_pipeline/04_biosample_matches_all.tsv \
  --review results/refactored_pipeline/04_biosample_review_all.tsv \
  --output-dir analysis_tmp/biosample_raw_audit \
  --target-organism Xanthomonas
```

输入含义：

- `--raw-input`：script 10 生成的 raw BioSample 候选结果。
- `--identifiers`：script 09 生成的 identifier candidate table，包括 `include_for_search=no` 的低置信证据。
- `--matches`：script 11 生成的 accepted matches，可选但推荐提供。
- `--review`：script 11 生成的 rejected/review rows，可选但推荐提供。
- `--target-organism`：当前项目为 `Xanthomonas`；未来扩展全 NCPPB 时可按 batch/row 改成其他 organism filter。

## 4. 逐条审核逻辑

### 4.1 元数据字段拆分

脚本从 raw row 中读取：

- `title`
- `organism`
- `identifiers`
- `infraspecies`
- `attributes`
- `metadata_text`

identifier pattern 和 query term 会分别在这些字段中匹配，并记录到 `best_identifier_fields` 与 `query_term_fields`。

### 4.2 Exact identifier pattern

脚本会为每个 strain 构建 pattern：

- 总是加入目标 `NCPPB number` pattern。
- 加入所有 `Other references` identifiers，包括 `include_for_search=no` 的低置信条目。
- 对分隔符做宽松匹配，例如空格、`:`、`-`、`_`、`.`、`/`。

因此 `ICMP204`、`ICMP 204`、`ICMP-204` 可以被视为同一 identifier 的候选变体；但 `ICMP ... 204` 这种分散共现不会被当作 exact identifier。

### 4.3 Query term 匹配

脚本会解析 search term 中的 fielded tokens，例如：

- `NCPPB[All Fields] AND 45[All Fields]`
- `(NCPPB[Text Word] AND 45[Text Word]) AND Xanthomonas[Organism]`

`Xanthomonas[Organism]` 作为目标 organism filter，不计入关键词 evidence。剩余 terms 用于解释 raw hit 来源：

- 全部 terms 出现但无 exact identifier：`query_terms_present_separately`
- 只有 prefix 出现：`prefix_only`
- 只有 suffix 出现：`suffix_only`
- 都没出现：`no_query_term_in_metadata`

这一步只解释检索噪声，不自动接受记录。

## 5. 输出文件

### 5.1 `raw_candidate_audit.tsv`

逐条 raw candidate 审核表。关键列：

- `prior_classification`：已有 script 11 分类，`accepted` 或 `review`。
- `organism_class`：`target_organism`、`non_target_organism`、`missing_organism`、`no_hit`。
- `best_identifier_match`：最强 exact identifier match。
- `keyword_match_class`：关键词匹配类型。
- `raw_audit_decision`：`supports_accept`、`supports_review`、`possible_false_negative_rescue`、`clear_noise`、`query_no_hit`。
- `audit_reason`：为什么给出该审核判断。
- `keyword_policy_signal`：给聚合推荐使用的行级信号。

### 5.2 `keyword_audit_summary.tsv`

按 single search term 聚合，适合检查具体 query 是否该保留。关键列：

- `raw_rows`
- `prior_accepted_rows`
- `prior_review_rows`
- `non_target_organism_rows`
- `possible_rescue_rows`
- `keyword_policy_recommendation`
- `recommendation_reason`

### 5.3 `prefix_keyword_recommendations.tsv`

按 `prefix + rule_name + confidence` 聚合，适合优化 script 09 的 identifier extraction policy。当前结果显示：

- `B / source_context_single_letter_code / low`：`fallback_only`，因为有极少 accepted 但噪声极高。
- `X / source_context_single_letter_code / low`：`disable_default`。
- `XP / contextual_reference_code / medium`：`disable_default`。
- `XC / contextual_reference_code / medium`：`fallback_only`。
- `NCPPB / ncppb_number / high`：`keep_strict_profile`。

### 5.4 `strain_raw_audit_summary.tsv`

按 NCPPB strain 聚合，用于人工审阅优先级排序。关键优先级：

- `P1_possible_false_negative_rescue`
- `P2_conflicting_identifier_review`
- `P3_target_taxon_without_exact_identifier`
- `confirmed_has_accepted_biosample`
- `low_priority_noise_or_no_hit`

### 5.5 `false_negative_rescue_candidates.tsv`

潜在假阴性救援表。当前主要是 `P2_target_taxon_query_terms_only`，即目标 organism 中出现 query terms，但没有 exact strain identifier。它们不能自动接受，但应人工检查是否 NCBI metadata 缺少标准 strain 字段，或本地 identifier extraction 需要增加别名规则。

## 6. 本次运行摘要

基于现有 full-scale BioSample raw data，本次 audit 结果为：

- raw rows：33,829
- `clear_noise`：31,673
- `query_no_hit`：1,242
- `supports_accept`：609
- `supports_review`：305
- prefix/rule recommendations：262 组
- `disable_default` prefix/rule groups：97 组
- `fallback_only` prefix/rule groups：8 组
- false-negative rescue candidates：148 行，当前均为 `P2_target_taxon_query_terms_only`

另外，脚本发现 3 条旧 `accepted` rows 需要重新人工复核，因为 metadata 同时指向 conflicting NCPPB number。这类情况应进入 final audit 的 curator review，而不是直接作为 confirmed accepted。

## 7. 接下来如何用它优化关键词

1. 先查看 `prefix_keyword_recommendations.tsv`：
   - 把 `disable_default` 的低置信 prefix/rule 从默认 BioSample 检索中关闭。
   - 把 `fallback_only` 保留给 no-hit strains 的 targeted review。

2. 再查看 `keyword_audit_summary.tsv`：
   - 对 raw rows 多、accepted rows 为 0、non-target rate 接近 1 的具体 search term，加入禁止或降级清单。
   - 对 accepted rows 存在但 review/accepted ratio 极高的 term，不再默认全量运行。

3. 最后查看 `false_negative_rescue_candidates.tsv`：
   - 逐条判断是否存在 NCBI metadata 格式问题、本地 identifier pattern 漏匹配，或需要补充 collection alias。
   - 只有人工确认后，才能把对应 extraction rule 从 `manual_review_only` 升级到更高置信度。

## 8. 仍需提升的地方

- 需要把 script 13 扩展到 Assembly，因为 proposal 的最终分类必须区分 complete genome、draft assembly、reads-only。
- 需要生成 final strain audit table，把 BioSample、SRA、BioProject、Assembly record sets 合并到 strain-level deliverable。
- 需要对 strict BioSample profile 做 pilot rerun，比较 `[Text Word] + Xanthomonas[Organism]` 是否保留现有 confirmed matches。
- 需要建立 query cache 与 resume 作为全 NCPPB 扩展前的硬性要求。
- 需要把 `disable_default/fallback_only/manual_review_only` policy 回写到 identifier extraction 或 query planning 步骤。
- 对 `Other references` 中的人名、本地编号、source label，应继续改进 extraction：优先识别 collection prefixes，低置信 local code 仅保留为 review evidence，不进入默认检索。
