# NCPPB–NCBI 数据获取与系统发育输入工作流

## 目标

这一步位于 V2.1 菌株身份匹配之后，解决两个不同问题：

1. 研究者怎样从确认的 NCPPB–BioSample 匹配获得实际序列；
2. 怎样为每个 NCPPB 菌株选择一个可用于后续系统发育分析的首选数据源。

## 数据库角色

| 数据库 | 在本项目中的角色 | 能否直接用于建树 |
|---|---|---|
| BioSample | 菌株身份锚点；把 NCPPB 标识符与提交样本联系起来 | 否 |
| Assembly | 已组装基因组及其质量/组装级别 | 是，经过 QC 后优先使用 |
| SRA | 原始测序 reads | 可以，但需要 reads QC、组装和 assembly QC |
| BioProject | 测序项目来源和实验背景 | 否，只用于 provenance |

BioProject 不能仅因 BioSample ELink 返回就被视为该菌株的测序项目。V2.1 只把以下项目提升为 `sequence_source_project`：

- Assembly 元数据中的 GenBank BioProject；
- SRA experiment 元数据中的 `<Bioproject>`。

RefSeq 通用注释项目标为 `annotation_project`；只由 BioSample ELink 返回的项目标为 `biosample_elink_only` 并要求复核。

## 工具分层

### 1. 匹配和元数据解析

V2.1 脚本使用 NCBI Entrez E-utilities：

- ESearch：候选 BioSample 召回；
- EFetch：读取 BioSample 结构化身份字段；
- ELink：从 BioSample 找到 Assembly、SRA 和候选 BioProject；
- ESummary：读取 Assembly/SRA/BioProject 元数据。

### 2. 下载 Assembly

使用 NCBI Datasets CLI。`sequence_resource_manifest.tsv` 已为每个 Assembly 生成命令，例如：

```bash
datasets download genome accession GCF_020783895.1 \
  --include genome \
  --filename NCPPB_101_GCF_020783895.1.zip
```

### 3. 下载 SRA reads

使用 NCBI SRA Toolkit：

```bash
prefetch SRR22272561
fasterq-dump SRR22272561 --split-files --outdir fastq/NCPPB_101
```

只有 `LIBRARY_STRATEGY=WGS` 且 `LIBRARY_SOURCE=GENOMIC`（或来源字段为空）的确认 SRA 才能成为 Assembly 缺失时的系统发育候选。

## 自动选择逻辑

每个 NCPPB 菌株只选择一类首选数据：

1. 有确认 Assembly：按 Complete Genome > Chromosome > Scaffold > Contig 排序；
2. 同级优先 RefSeq (`GCF_`)；
3. 再比较 contig N50；
4. 无 Assembly 时，选择报告碱基数最多的确认 WGS BioSample，并保留该 BioSample 的全部 runs；
5. 只有 provisional BioSample 时不自动纳入树；
6. BioSample metadata only 或无确认数据时不生成伪序列入口。

所有被选择的资源仍标记 `qc_required=yes`。身份匹配可靠不等于基因组质量合格。

## 当前 V2.1 结果

- 897 个当前 NCPPB 记录；
- 307 个菌株有首选 Assembly；
- 50 个菌株只有 WGS SRA，需要组装；
- 3 个确认 BioSample 只有元数据，没有可用 Assembly/WGS；
- 25 个菌株只有 provisional identity，需要先解决身份；
- 512 个菌株目前没有确认公共序列。

因此，目前理论上有 357 个菌株可以进入下一阶段的基因组 QC；这不是“357 个已经可以直接建树”，而是 307 个现成 assembly 加 50 个需要从 reads 组装的候选。

## 产出文件

- `sequence_resource_manifest.tsv`：长表；每个 BioSample/Assembly/SRA/BioProject 一行，包含身份状态、元数据、下载工具和命令；
- `phylogeny_input_manifest.tsv`：每个 NCPPB 菌株一行；给出首选序列、选择原因和是否准备好进入 QC；
- `bioproject_mapping.tsv`：将真实测序项目、RefSeq 注释项目和 ELink-only 项目分开；
- `sequence_retrieval_summary.md`：当前数据获取能力摘要。

## 后续建树边界

不要立即把 357 个文件直接交给一个建树程序。下一阶段至少还需要：

1. 下载完整性和 accession 版本检查；
2. raw-read QC 与 50 个 SRA 菌株的统一组装；
3. assembly 长度、contig 数、N50、完整度和污染检查；
4. 去除重复 BioSample/重复菌株；
5. 根据研究问题决定做全属 marker/core-genome tree，还是按 species/pathovar 做 core-SNP tree；
6. 固定软件版本、参数、输入文件名/获取日期和排除理由；如项目需要内容指纹，可选择记录 SHA-256，但主流程不要求哈希校验。

当前本机尚未安装 `datasets`、`prefetch` 和 `fasterq-dump`；TSV 中的命令是可审计的下载计划，不代表序列文件已经下载。
