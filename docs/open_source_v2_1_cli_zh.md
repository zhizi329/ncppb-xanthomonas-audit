# V2.1 开源命令行工作流

## 1. 这个入口能否从 HTML 一直运行到最终表

可以。`scripts/run_ncppb_audit_v2.py` 以用户提供的 NCPPB catalogue HTML 为唯一必需数据输入。启用 `--run-ncbi` 后，它会依次完成：

```text
HTML catalogue
  -> strain / Other-reference parsing
  -> identifier extraction and risk classification
  -> two-track BioSample query plan
  -> NCBI query execution and BioSample retrieval
  -> structured identity matching
  -> Assembly / SRA / BioProject expansion
  -> one-row-per-strain supervisor table
  -> sequence-download and phylogeny-input manifests
```

V1 master 和 V1 sequence table 都是可选回归基线，不是运行前提。

## 2. 完整运行命令

推荐交互式输入 API key：

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html /absolute/path/NCPPB_catalogue.html \
  --run-ncbi \
  --email researcher@example.org \
  --prompt-api-key \
  --outdir runs/audit/my_v2_1_run
```

程序会显示：

```text
NCBI API key (input hidden; press Enter to continue without one):
```

输入不会回显，也不会写入输出、cache key 或 manifest。API key 是可选的；直接按 Enter 会以较低请求速率继续。

非交互环境可以使用：

```bash
export NCBI_EMAIL=researcher@example.org
export NCBI_API_KEY=your_key
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html /absolute/path/NCPPB_catalogue.html \
  --run-ncbi \
  --outdir runs/audit/my_v2_1_run
```

不建议把 key 直接写在命令行 `--api-key` 后，因为它可能进入 shell history 或进程列表。

## 3. HTML 与哈希策略

- `--catalogue-html` 是必需参数；仓库不再隐式读取作者本地 HTML。
- 任意结构符合 NCPPB catalogue 的用户 HTML 都可以运行。
- 默认不计算或校验 HTML SHA-256。
- 验证器不检查 HTML 是否等于作者使用的历史文件。
- 可选 `--record-input-hash` 仅把 SHA-256 写入 provenance 字段，不会形成拒绝条件。

## 4. 可选历史回归基线

普通开源用户不需要 V1：

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html catalogue.html \
  --run-ncbi \
  --email researcher@example.org \
  --prompt-api-key
```

仓库只保留小型 898-row catalogue baseline，不再维护被替代的 V1 sequence-output 目录。冻结的 V2.1.1 run 已保留完整历史回归证据。历史 accession 只用于 regression protection，不参与没有完整 baseline 的全新运行。

## 5. 中间文件

### HTML 解析阶段

| 文件 | 内容 |
|---|---|
| `catalogue_strains.tsv` | 当前 HTML 中每个 NCPPB strain 一行 |
| `other_reference_clauses.tsv` | 保留 `<br>` 边界的 Other references clauses |
| `catalogue_snapshot_diff.tsv` | 有 V1 时记录变化；无 V1 时标为 `current_snapshot_no_v1_baseline` |
| `strain_identifiers.tsv` | 主编号、正式保藏号、donor/isolate code及强度/风险 |
| `parser_review_queue.tsv` | 冲突或不可自动解释的标识符 |

### NCBI 检索阶段

| 文件 | 内容 |
|---|---|
| `ncbi_query_plan.tsv` | 可复现查询词、查询轨道、分页上限和本地匹配规则 |
| `ncbi_query_execution.tsv` | reported count、实际UID数、截断、warning和错误状态 |
| `biosample_candidates.tsv` | 原始候选及结构化BioSample身份字段 |
| `biosample_match_decisions.tsv` | 每个strain–BioSample候选的accept/review/reject证据 |
| `linked_ncbi_records.tsv` | BioSample通过ELink/ESummary得到的Assembly/SRA/BioProject元数据 |

### 审核与回归阶段

| 文件 | 内容 |
|---|---|
| `manual_review_queue.tsv` | 需要人工判断的菌株级问题 |
| `v1_v2_comparison.tsv` | 提供V1基线时的菌株级比较 |
| `v1_regression_recall_audit.tsv` | 提供V1基线时逐个历史配对的召回控制 |
| `v1_v2_accession_changes.tsv` | 新增、移除和降级的accession |

## 6. 最终文件

### `supervisor_sequence_availability.tsv`

核心交付表。当前 HTML 中每个 NCPPB strain 恰好一行，分别列出：

- confirmed BioSample；
- provisional BioSample；
- NCPPB-number 和 Other-references 两个发现轨道；
- Assembly及assembly level；
- SRA run；
- 经Assembly/SRA元数据确认的sequence-source BioProject；
- sequence-availability category；
- taxonomy/manual-review状态。

### `sequence_resource_manifest.tsv`

长表。每个BioSample、Assembly、SRA run和分类后的BioProject一行，包含NCBI URL、下载工具、下载命令、身份状态和是否被选择用于系统发育准备。

### `phylogeny_input_manifest.tsv`

当前HTML每个NCPPB strain一行。自动选择一个最高优先级Assembly，或在没有Assembly时选择确认的WGS runs。该表是下一阶段QC/组装的输入计划，不代表未经QC即可直接建树。

### `bioproject_mapping.tsv`

区分：

- `sequence_source_project`；
- `annotation_project`；
- `biosample_elink_only`。

只有第一类进入主管主表的确认BioProject列。

## 7. 数量口径

“有数据的菌株数”和“匹配结果数”必须分开：

- V1：370个NCPPB菌株至少有一个确认BioSample；612是接受证据行数；去重后为552个strain–BioSample配对、549个唯一BioSample；
- V2.1：360个NCPPB菌株至少有一个确认BioSample；533个确认strain–BioSample配对，目前也是533个唯一BioSample。

导师问题“每个NCPPB strain有哪些序列”应引用菌株数和`supervisor_sequence_availability.tsv`；方法学审计才引用candidate/decision/pair数量。

## 8. 验证

通用开源运行：

```bash
python3 scripts/validate_ncppb_audit_v2.py --outdir runs/audit/my_v2_1_run
```

项目特定回归检查可以附加：

```bash
python3 scripts/validate_ncppb_audit_v2.py \
  --outdir runs/audit/2026-07-10_v2.1.1 \
  --expected-current-records 897 \
  --expected-missing-number "NCPPB 4416"
```

验证包括查询计划覆盖、零静默截断、候选/链接错误、accepted证据强度、确认BioSample资源覆盖、系统发育选择合法性和BioProject provenance分类。
