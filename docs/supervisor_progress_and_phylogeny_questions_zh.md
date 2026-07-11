# NCPPB–NCBI Xanthomonas 项目进展与发育分析衔接

## 一句话概括

当前项目已经完成的是一套可复现的“菌株身份与公共序列可用性审计”：从 NCPPB 目录中的每一株菌出发，用 NCPPB 编号和其他保藏号在 NCBI BioSample 中寻找同一株菌，再沿 NCBI 的正式数据库链接查找 Assembly、SRA 和 BioProject。当前尚未下载基因组 FASTA/FASTQ，也没有进行序列质控、比对、ANI 或系统发育树构建。

## 1. 汇报时应采用哪个版本

最新、已重新执行并通过验证的是 **V2.1**：

- 当前 NCPPB HTML 快照：897 条记录；
- 源 HTML SHA-256：`093d40d70e9b1e32161cde8c49cec694b7682c9e45c8199ff4cad977543b918e`；
- 运行版本：`2.1.0-dev`；
- 1,376/1,376 条 NCBI 查询均成功；
- 查询截断、BioSample candidate error、Assembly/SRA/BioProject link error 均为 0；
- 本地验证脚本已再次运行并通过。

较早的 898 株 interim 工作簿已删除，不能作为“最新数字”引用。旧表中的 NCPPB 4416 在当前 HTML 快照中已不存在，因此 V2.1 只在回归证据中保留这一差异，没有把它强行补回当前主管表。

## 2. 数据是怎样得到的

### 第一步：冻结 NCPPB 输入

流程从保存的 NCPPB catalogue HTML 开始，而不是每次直接读取变化中的网页。这样每次运行都能用文件哈希说明究竟使用了哪一版目录。

### 第二步：解析每一株菌和所有可用标识符

一条目录记录被整理为一个 NCPPB strain，并保留：

- NCPPB 编号；
- 当前名称、接收时名称和替代名称；
- 宿主、国家；
- `Other references` 中的其他保藏号、donor reference 和 isolate code；
- 原始目录文本及来源位置。

V2.1 共解析出 897 株、1,585 个 other-reference clauses 和 3,144 个 identifier rows，其中 1,164 个 other-reference identifiers 可用于检索。标识符强度被区分为 NCPPB 主编号、正式保藏号和仅供候选检索的局部编号，避免把普通数字或人名误当成菌株号。

### 第三步：用两条轨道检索 NCBI BioSample

流程不是只搜物种名，而是以菌株标识符为核心：

1. `ncppb_number` 轨道：批量收集带 NCPPB 前缀的记录，并对每株执行完整编号形式查询，如 `NCPPB 45`、`NCPPB45`、`NCPPB:45`；
2. `other_references` 轨道：利用 ICMP、LMG、CFBP、ATCC 等等价保藏号，以及保守处理的 donor/isolate code。

NCBI 搜索命中只算 candidate，不自动证明是同一株菌。

### 第四步：在结构化身份字段中验证菌株身份

只有完整标识符出现在 BioSample 的 `strain`、`isolate`、`culture_collection`、`bio_material`、`sample_name`、`identifiers` 或身份别名字段中，才可形成强身份匹配。标题中出现编号、局部 donor code、冲突 NCPPB 编号等情况进入人工复核，不混入 confirmed 统计。

当前 874 个 candidate decisions 中：

- 533 个接受；
- 301 个拒绝；
- 40 个 candidate decision 需要复核。

533 个确认 BioSample 覆盖 360 个 NCPPB strain。一个 strain 可以对应多个 BioSample，因此不能把 BioSample 数量当成菌株数量。

### 第五步：由 BioSample 扩展到序列记录

对确认或 provisional BioSample，流程使用 NCBI ELink 查找：

- Assembly：GCA/GCF 基因组组装；
- SRA：SRR/ERR/DRR 原始测序 reads；
- BioProject：项目归属。

confirmed 与 provisional 的下游链接分别保存，不会混在一起。这里仍然只收集 accession 和元数据，不下载实际序列。

## 3. 最新结果应该怎样解释

V2.1 的 897 株分为：

| 类别 | 菌株数 | 含义 |
|---|---:|---|
| Complete genome available | 119 | 至少有一个 Complete Genome 级别组装 |
| Chromosome-level assembly available | 3 | 有 chromosome-level 组装但没有 Complete Genome |
| Draft assembly available | 185 | 有 contig/scaffold 等 draft 组装 |
| Raw reads only | 50 | 没有 Assembly，但有确认的 WGS SRA reads |
| BioSample metadata only | 3 | 身份已确认，但没有链接到 Assembly 或 SRA |
| Ambiguous needs review | 25 | 只有 provisional/冲突证据，尚不能计入确认数据集 |
| No confirmed public data | 512 | 当前规则未确认到该菌株的公共序列记录 |

因此：

- 360 株有确认 BioSample；
- 307 株有确认 Assembly；
- 317 株有确认 SRA；
- 358 株有确认 BioProject；
- 目前发现 394 个不同 Assembly accession，对应 307 株；其中 68 株有不止一个 Assembly，需要在构树前选择代表组装；
- 50 株 `raw_reads_only` 的确认 SRA 均包含 WGS strategy，但需要下载、质控和组装后才能进入全基因组树。

`有 SRA` 不应直接写成 `有基因组`。SRA 链接中也可能出现 RNA-Seq 等实验；V2.1 的 50 株 raw-read-only 恰好都有 WGS，但后续下载脚本仍应明确只保留 genomic WGS/WGA 数据。

## 4. 问题①：现在拿到的是完整基因组，还是 16S/gyrB/rpoD？

答案是：**当前主流程主要审计全基因组相关数据，不是单基因数据库检索。**

- Assembly accession 是全基因组组装记录，但只有 119 株达到 `Complete Genome`；另外 3 株为 chromosome level、185 株为 draft assembly。
- SRA accession 是原始 reads，不等于已经组装好的基因组；50 株只有 WGS reads，需要先组装。
- 当前流程没有系统检索 NCBI Nucleotide/GenBank，因此不能据此判断 897 株中哪些有 16S、gyrB、rpoD 等单基因序列。
- 旧 NCPPB master 中只有 16 株带有 catalogue sequence links，内容确实包括 16S、gyrB、rpoD、dnaK、fyuA 等单基因和少量 genomic DNA accession；但这些链接没有被 V2.1 主表系统传播，也不能代表完整的 NCBI 单基因覆盖率。

如果导师选择单基因树，必须新增一个独立步骤：使用所有已确认菌株别名检索 NCBI Nucleotide，按 locus、长度、方向、覆盖区段和菌株证据过滤，再评估哪个 marker 的覆盖率足够。现有 Assembly/SRA 表不能直接回答这个问题。

## 5. 当前结果与发育树的直接关系

当前审计表是发育分析的“样本清单和 accession 路由表”。它解决了构树前最容易出错的身份问题：哪些 NCBI 记录能够可信地对应到哪一株 NCPPB 菌。

但从 accession 到树之间仍有以下步骤：

```text
确认菌株集合
  -> 选择每株代表 Assembly，或下载 WGS reads 并组装
  -> 基因组质量控制与污染检查
  -> 去除重复、衍生株、明显分类错误和不合格基因组
  -> 决定全属树、species-complex 树或种内树
  -> 选择 core-gene / core-genome SNP / 单基因方法
  -> 构树和支持度评估
  -> 导出 iTOL tree 与 metadata annotation 文件
```

iTOL 只负责展示和标注，不负责解决序列选择、比对质量、模型或菌株身份问题。

## 6. 对发育分析路线的建议

如果研究问题是 NCPPB Xanthomonas 收藏的基因组多样性和分类关系，优先建议全基因组路线，而不是仅用 16S：

1. 第一阶段使用 307 株已有 Assembly 的 confirmed strains；
2. 每株只选择一个质量最佳的代表组装，保留 accession 选择记录；
3. 加入适当的 type/reference genomes 和 outgroup，不能只依赖 NCPPB 子集解释分类；
4. 先用 ANI 检查物种归属和疑似错标，再按物种或 species complex 构建 core-genome/core-gene tree；
5. 50 株 raw-WGS-only 可在统一组装和质控后作为第二阶段补入；
6. genus-wide overview 和 species-level fine tree 最好分开，因为把差异很大的整个属强行做一个核心基因组，可能导致共享核心过小并降低种内分辨率。

如果导师只要求一张快速概览树，需要先明确它回答的是“属内大类群关系”还是“菌株间精细关系”。这两个目标不能简单用同一套 marker 和过滤阈值代替。

## 7. 元数据分组和 iTOL 标注的现状

目录中已有一定标注基础：

- host：V2.1 中 855/897 非空，原始值约 380 种；
- country：875/897 非空，原始值约 115 种；
- 旧 master 的 `year_added`：895/898 非空，但这是加入 NCPPB 的年份，不一定是分离年份；
- 旧 master 的 pathovar：686/898 非空；
- type strain：33 株；pathotype strain：151 株。

这些字段可生成 iTOL 色条，但需要先标准化。尤其要注意：

- host 名称存在同物异名、只写属名和不同层级混用；
- country 需要统一历史地名和拼写；
- `year_added`、BioSample `collection_date`、NCBI submission/create date 是三种不同时间，不能混用；
- pathovar/pathotype 是分类或表型标签，不能自动等同于“已经实验验证的致病性”；
- V2.1 主管表目前没有把 collection date、host、country、pathovar 等全部整理成最终 iTOL annotation 表。

## 8. 当前仍存在、需要导师或人工决定的问题

### A. 当前审计尚未完全冻结

- 83 株需要人工复核，其中包括 provisional 身份问题和 60 株 taxonomy review；
- 18 条 identifier-collision parser review 仍为空，例如同一 ICMP/LMG/ATCC 号映射到两个 NCPPB 记录；
- 当前 HTML 比旧 master 少 NCPPB 4416，需要决定最终论文以哪一个目录快照为准；
- 技术验证已通过，但“通过验证”不等于这些生物学歧义已经人工解决。

### B. 进入构树前必须定义纳入规则

- 只纳入 confirmed strains，还是允许人工确认后的 provisional strains？
- 分类名称不一致但菌株编号强匹配的记录如何处理？
- 一株多个 BioSample/Assembly 时，选择 RefSeq、最新版本还是质量最佳版本？
- 采用哪些最低质量阈值：完整度、污染、N50、contig 数、基因组长度和异常覆盖？
- raw WGS 是否纳入；如果纳入，采用怎样的统一质控和组装流程？
- 是否排除 mutant、衍生株、噬菌体记录和混合/污染样本？

### C. 必须先定义树回答什么问题

- 一张全属概览树，还是按 species/species complex 分树？
- 使用 16S/gyrB/rpoD、保守单拷贝核心基因、core-genome SNP，还是其他方法？
- 是否需要加入非 NCPPB 的 type/reference genomes 和 outgroup？
- 是否需要 bootstrap/其他支持度，以及最低报告标准？

### D. ANI、核心基因组和 iTOL 的范围

- ANI 是用来核查物种边界和错标，不是系统发育树本身；是否纳入论文正式结果？
- 是否做全数据集 ANI，还是只对名称冲突和每个 species complex 做 ANI？
- iTOL 是否只做物种/pathovar 色条，还是还要展示 host、country、年份、数据质量、type/pathotype、致病性？
- 是否需要把 metadata 与树的聚类关系做统计检验，还是只做描述性展示？

## 9. 建议当面向导师确认的问题

1. 本项目最终的系统发育问题是什么：全属分类概览，还是某些 species complex 内的菌株关系？
2. 导师希望使用全基因组数据，还是指定 16S、gyrB、rpoD 等单基因？如果是单基因，目标 locus 和最低覆盖率是什么？
3. 是否接受以 307 株现有 Assembly 为第一阶段，50 株 raw WGS 以后统一组装再补充？
4. 是否需要 ANI；若需要，是全体筛查还是只处理分类名称冲突和近缘组？
5. 是只交付一张树并在 iTOL 美化，还是必须加入 host、country、时间、pathovar/type/pathotype/致病性等注释？
6. “年份”具体指分离年份、加入 NCPPB 的年份，还是 NCBI 提交年份？
7. “致病性”允许用 pathovar/pathotype 作为标签，还是必须寻找实验验证数据？
8. 83 株 manual review 和 18 条 identifier collision 是否必须全部解决后才能冻结构树样本？
9. 最终目录以当前 897 株快照为准，还是把旧快照中的 NCPPB 4416 作为历史记录保留？
10. 每株多个 Assembly 时采用什么优先规则和最低基因组质量标准？

## 10. 可直接用于口头汇报的短版

> 我们现在完成的不是发育树本身，而是 NCPPB 菌株与 NCBI 公共序列之间的可复现审计。最新 V2.1 从当前 897 条 NCPPB 目录记录出发，用 NCPPB 编号和其他正式保藏号检索 BioSample，并在结构化菌株字段中确认身份，再通过 NCBI ELink 扩展到 Assembly、SRA 和 BioProject。全部 1,376 条查询均成功且没有截断。现在确认了 533 个 BioSample，覆盖 360 株；其中 307 株已有全基因组 Assembly，50 株只有 WGS raw reads，3 株只有 BioSample 元数据。Assembly 中按菌株最高级别统计为 119 株 complete genome、3 株 chromosome level、185 株 draft。当前流程没有系统检索 16S、gyrB、rpoD 等 Nucleotide 单基因记录，也还没有下载序列和构树。下一步要先请导师确定是做全基因组还是单基因、是一张全属概览树还是按 species complex 分析、是否加入 ANI 和核心基因组分析，以及 iTOL 是否需要结合宿主、地区、年份和致病性等信息。同时还有 83 株人工复核、18 条标识符冲突以及多 Assembly 选择和质量控制规则需要在冻结构树数据集前解决。
