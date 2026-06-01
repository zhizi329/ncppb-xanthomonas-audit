# Week 3 工作汇报草稿（中文版，待人工改写）

## 本周工作定位

Week 3 的工作主要是在 Week 2 smoke test 的基础上查漏补缺。Week 2 已经证明脚本可以通过 NCBI E-utilities 检索到 BioSample、Assembly 和 SRA 等候选 ID，但当时的结果只能说明“有候选记录”，还不能说明这些记录一定属于某一个 NCPPB strain。

Week 3 的核心任务是优化search strategy：先对前 30 个 NCPPB Xanthomonas strains 做 pilot table，记录不同检索方式带来的问题，再确定更合理的检索和筛选模式。这个过程包括一次明显的弯路：先尝试使用 NCPPB 网页和 master table 中几乎所有可见关键词进行检索，随后发现这种方式会产生大量无意义候选，最后收紧为 BioSample-only identifier search。

## 本周尝试过的两种检索模式

### 第一轮：broad keyword harvest

第一轮的思路是尽可能不漏掉任何关键词，所以使用了 NCPPB catalogue 和网页html文件中能提取到的大量关键词，包括 NCPPB number、compact NCPPB number、catalogue name、name as received、other name、other references，以及部分当前名称和历史名称组合。检索数据库也比较宽，包括 BioSample、Assembly 和 SRA。

这一轮的结果是 7728 条 raw candidates，考虑到仅仅检索了30个strain，如果扩大到整个ncppb数据库，900条strain将会消耗大量的检索命令资源，而且7000条数量的。这个数量也说明了检索方式不合理，因为前 30 个 strain 不应该产生这么多需要人工判断的候选记录。检查结果后发现，大部分候选来自物种名、pathovar 名或其他宽泛文本。这些候选很多只是 taxon-level hit，或者是非 Xanthomonas 记录，或者是同一物种下其他 NCPPB 编号的记录。它们对确认某一个具体 NCPPB strain 没有足够意义。

但是这一步仍然有价值，因为它证明了一个问题：扩大检索词范围并不会明显增加最终有效结果。7728 条 raw candidates 经过 strict filtering 后，仍然只有 10 个 strain 能得到 confirmed record set。也就是说，真正决定结果质量的不是 broad keyword recall，而是 strain-level identifier 是否能在 metadata 中被确认。

### 第二轮：BioSample-only identifier harvest

第二轮改为只检索 BioSample，并且只使用编号型关键词。最终保留的关键词只有两类：

1. `NCPPB + number`，例如 `NCPPB 45`。
2. `Other references` 或其他 collection number 字段中出现的编号型信息，例如 `LMG 33367`、`NBC5720`、`ICMP 204`。

这一轮不再使用 species name、pathovar name、catalogue name、host、country 或 broad taxonomic labels 作为 NCBI 检索词。原因是这些词会产生大量 taxon-level candidates，但不能证明 strain identity。

新的查询格式把 identifier 拆成 prefix 和 number，例如：

```text
NCPPB[All Fields] AND 45[All Fields]
LMG[All Fields] AND 33367[All Fields]
NBC[All Fields] AND 5720[All Fields]
```

这样做的目的是覆盖不同 metadata 写法，例如 `NCPPB 45`、`NCPPB45`、`NCPPB:45` 或 `NCPPB_Number: 45`。这种检索方式仍然会带来假阳性，但假阳性会在本地筛选阶段重新过滤。

第二轮前 30 个 strain 的结果如下：

| 指标 | 数量 |
|---|---:|
| Planned BioSample identifier queries | 42 |
| Raw BioSample candidate rows | 132 |
| Accepted BioSample records | 11 |
| Review rows, including no-match summaries | 141 |
| BioSample-centred record sets | 11 |
| 有 confirmed BioSample record set 的 strains | 10 / 30 |

两轮检索的最终有效 strain 数相同，都是 10 / 30。这说明第二轮虽然 raw candidate 数量大幅下降，但没有损失当前 strict filtering 能确认的有效结果。

## 关键词表格的获得逻辑

### 1. NCPPB 原始网页到 master table

原始输入是保存下来的 NCPPB 网页文件：

```text
data/raw/ncppbresult.html
```

`00_extract_ncppb_html.py` 从这个 HTML 中提取每个 strain 的网页记录，输出：

```text
data/raw/ncppb_catalogue.csv
```

随后 `01_clean_ncppb_catalogue.py` 把 raw catalogue 清理成项目 master table：

```text
data/processed/ncppb_xanthomonas_master.csv
```

master table 中保留了每个 strain 的核心字段，包括 `ncppb_number`、`current_name`、`name_as_received`、`alternative_names`、`host`、`country`、`other_collection_numbers`、`other_references` 和 `raw_record_text`。这些字段用于后续检索、筛选和人工复核。

### 2. Week 2 general search terms

`02_make_search_terms.py` 会从 master table 生成一个较宽的 search term table：

```text
data/interim/search_terms.tsv
```

这个表最初用于 Week 2 smoke test，包含 NCPPB number、compact number、collection name plus number、current name plus number、received name plus number、alternative name plus number，以及 other collection numbers。

这个表的作用是保留 strain 顺序和早期探索性关键词。Week 3 后期并没有直接把这些 broad terms 全部用于最终 harvest，因为其中的 name-based terms 会导致大量无意义候选。

### 3. HTML keyword audit

为了检查 master table 是否漏掉网页中的可见信息，本周增加了：

```text
scripts/02_extract_html_keyword_audit.py
```

这个脚本直接读取原始 HTML，并把每个 strain 页面中能看见的 label/value 信息导出成长表：

```text
data/interim/ncppb_html_keyword_audit.tsv
```

这个 audit table 会记录 `catalogue_name`、`name_as_received`、`other_name`、`host`、`country`、`notes`、`other_references`、`raw_record_text` 等网页字段。它还会从网页文本中识别常见 culture collection identifiers，例如 ICMP、LMG、DSM、ATCC、CFBP 等。

这个表的用途不是直接把所有关键词都拿去 NCBI 检索，而是帮助确认哪些字段存在、哪些编号可能对检索有价值。

### 4. Week 3 final BioSample query plan

最终 Week 3 使用的是一个更窄的 query plan：

```text
results/week3_ncbi_biosample_query_plan_30.tsv
```

这个表由 `03_make_biosample_query_plan.py` 生成。逻辑是：

1. 从 `search_terms.tsv` 只取前 30 个 unique NCPPB strain，保证 pilot strain 顺序一致。
2. 从 master table 找到这些 strain 的完整记录。
3. 为每个 strain 生成一个 `NCPPB + number` 查询。
4. 从 `other_collection_numbers` 和 `other_references` 中提取编号型 identifier。
5. 把 `NBC5720` 这类紧凑写法标准化为 `NBC 5720`。
6. 把每个 identifier 转成 `prefix[All Fields] AND number[All Fields]` 格式。
7. 只针对 BioSample 生成查询，不对 Assembly/SRA 直接做 keyword search。

例如 `NCPPB 101` 的 planned queries 是：

```text
NCPPB[All Fields] AND 101[All Fields]
ICMP[All Fields] AND 204[All Fields]
LMG[All Fields] AND 673[All Fields]
DSM[All Fields] AND 18958[All Fields]
```

## NCBI harvest 的技术逻辑

`03_ncbi_harvest_candidates.py` 是联网步骤。它读取 query plan 背后的 strain context，并通过 NCBI E-utilities 查询 BioSample。

每个 query 先执行 `ESearch`，得到 BioSample UID 列表；然后执行 `ESummary`，取回 metadata summary。脚本保存的是 metadata，不下载 sequence files。

raw candidate 表包括以下关键信息：

- `ncppb_number`：目标 NCPPB strain。
- `query_label`：检索词来源，例如 `ncppb_number`、`other_collection_number`、`other_reference_identifier`。
- `search_term`：实际提交给 NCBI 的查询字符串。
- `ncbi_db`：当前固定为 `biosample`。
- `ncbi_uid` 和 `ncbi_accession`：NCBI 内部 ID 和 BioSample accession。
- `organism`、`taxid`、`title`、`evidence_text`、`metadata_text`：后续筛选所需的 metadata。

raw candidate 只是候选，不代表确认匹配。

## Filtering 的技术逻辑

`04_ncbi_classify_candidates.py` 是本地筛选步骤，不再访问 NCBI。它读取 raw candidate table，然后为每个 NCPPB strain 建立一个 `StrainContext`。

`StrainContext` 中最重要的是 exact identifier list，包括：

- 标准 NCPPB identifier，例如 `NCPPB 45`。
- `other_collection_numbers` 中的编号，例如 `ICMP 204`。
- `Other references` 中提取出来的 donor/reference identifiers，例如 `NBC 5720`。

筛选规则按以下顺序执行：

1. 如果 `organism` 字段存在但不是 Xanthomonas，标记为 `ambiguous`，原因是 `non_xanthomonas_organism`。
2. 如果 metadata text 中出现当前 strain 的 exact NCPPB number 或等价 identifier，标记为 `strong_strain_match`。
3. 如果 metadata text 中出现其他 NCPPB number，例如目标是 `NCPPB 45`，但记录中写的是 `NCPPB 3709`，标记为 `conflicting_ncppb_number`。
4. 如果记录只是 Xanthomonas 相关，但没有 exact strain identifier，标记为 `taxon_level_only`。
5. 如果一个 strain 没有任何 accepted match，则添加一条 `no_accepted_strain_level_match` summary row。

这种筛选方式的重点是避免把同一物种或同一 pathovar 下的其他 strain 错误算作目标 NCPPB strain。

## BioSample、SRA 和 Assembly 的关联逻辑

Week 3 最终检索阶段只直接查询 BioSample。原因是 BioSample 是 NCBI 中最接近“样本/strain metadata”的层级，通常包含 strain identifier、organism、isolate、culture collection number 等信息。相比之下，Assembly 和 SRA 记录有时不会重复完整 strain identifier，而是通过 BioSample accession 与样本记录相连。

因此合理的关联顺序应该是：

```text
NCPPB strain
  -> exact identifier search in BioSample
  -> accepted BioSample accession
  -> linked Assembly/SRA records through BioSample accession
  -> final data availability category
```

也就是说，不能用 species/pathovar keyword 直接在 Assembly 或 SRA 中检索后就认为是目标 strain。更稳妥的做法是先确认 BioSample，再用 accepted BioSample accession 去关联其他库。

`05_ncbi_group_record_sets.py` 的设计就是按 BioSample-centred record set 汇总结果。如果输入中包含 accepted BioSample、Assembly 和 SRA 记录，并且它们共享同一个 BioSample accession，那么脚本会把它们归为同一个 record set，并根据可用数据类型给出分类：

- 有 complete genome assembly -> `complete_genome_available`
- 有 contig/scaffold/chromosome assembly -> `draft_assembly_available` 或相关 assembly category
- 有 SRA 但无 assembly -> `reads_only`
- 只有 BioSample -> `biosample_only`

在当前 Week 3 final run 中，harvest 只查询 BioSample，所以前 30 个 pilot 的 best category 都是 `biosample_only` 或 `no_confirmed_public_data_found`。下一步如果要判断 complete genome、draft assembly 或 reads only，需要从 accepted BioSample accession 出发，再查询 Assembly/SRA linkage，而不是重新使用 broad strain keywords 检索 Assembly/SRA。

## 前 30 个 strain 的当前结果

目前有 accepted BioSample record sets 的 strains 是：

```text
NCPPB 45
NCPPB 101
NCPPB 113
NCPPB 151
NCPPB 206
NCPPB 211
NCPPB 220
NCPPB 226
NCPPB 230
NCPPB 232
```

其中 `NCPPB 206` 有两个 accepted BioSample record sets，需要后续人工判断它们是否代表同一 strain 的不同提交记录，还是不同来源的记录。

`NCPPB 208` 的 `Other references` 中包含 `PC5`。这个编号被转换为 `PC[All Fields] AND 5[All Fields]` 后返回了大量候选，但筛选阶段没有确认出有效 match。这说明短 donor reference 能提高 recall，但也可能显著增加 false positives，因此需要在 full-scale run 前决定是否对短编号设置额外规则。

## 本周遇到的主要困难

第一个困难是 broad keyword search 过宽。使用 catalogue name、species name、pathovar name 等关键词可以返回大量 NCBI 记录，但大多数只说明 taxon-level similarity，不能证明 strain identity。

第二个困难是 `Other references` 中的编号格式不统一。例如 `NBC5720`、`LMG 33367`、`NCPPB:45` 和 `NCPPB45` 需要被统一成 prefix + number 的形式检索，同时又要在筛选阶段保持 exact identifier 判断。

第三个困难是短编号假阳性。例如 `PC5` 这种 identifier 太短，容易返回大量无关 BioSample。它不能简单删除，因为它确实来自 NCPPB record；但也不能自动接受，必须保留为 review evidence。

第四个困难是跨库 metadata 不一定完整。BioSample 中可能有 strain identifier，但 Assembly 或 SRA 不一定重复这个编号。因此后续关联 Assembly/SRA 时应使用 accepted BioSample accession，而不是直接对 Assembly/SRA 做 broad keyword search。

## 下一步计划

下一步应先人工复核 11 个 accepted BioSample record sets，特别是 `NCPPB 206` 的两个 BioSample record sets，以及 `NCPPB 208` 的短编号 `PC5` 是否应该继续作为自动检索关键词。

确认 BioSample identifier search 和 filtering 规则稳定后，再增加一个 linkage step：用 accepted BioSample accession 去查找 Assembly 和 SRA，并把 linked records 加入 BioSample-centred record set。这样才能在 full-scale audit 中区分 complete genome、draft assembly、reads only 和 BioSample-only。

完整运行后，可以生成 final audit table、summary statistics 和 figures，并在报告中区分 confirmed public data、review candidates 和 no confirmed public data found。
