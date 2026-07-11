# V2.1 全量验证与召回审计

## 结论

V2.1 已在当前 897 条 NCPPB HTML 快照上完成全量运行并通过硬性校验。它不能证明对 NCBI 中所有潜在记录达到绝对 100% 召回，但可以排除先前已经观察到的低召回机制，并在 V1 历史对照范围内证明：所有仍满足 V2.1 确认标准的历史配对都被新检索轨道直接找回，没有确认项依赖历史 accession 兜底。

## 全量执行质量

- 查询计划：1376 条，1376 个唯一 query ID；
- 查询执行：1376/1376 成功；
- 截断查询：0；
- BioSample candidate error：0；
- Assembly/SRA/BioProject link error：0；
- 当前目录记录：897；
- `NCPPB 4416`：仅标记为相对 V1 快照缺失，不插入当前主管表。

816 个逐编号查询出现至少一个 `QuotedPhraseNotFound` warning。这不是截断或请求失败，而是 NCBI 告知某个空格/冒号变体未建 phrase index。V2.1 同时保留紧连形式、批量 NCPPB 前缀收集和本地结构化精确验证，因此 warning 被记录但不被误当成零风险。所有 query 的 reported count 与 retrieved UID count 均通过零截断检查。

## V1 历史配对回归

V1 共有 552 个菌株–BioSample 配对：

| 指标 | 诊断性 V2 | V2.1 |
|---|---:|---:|
| 被新 NCPPB/Other-reference 轨道直接找回 | 497 | 535 |
| 需要历史 accession 兜底 | 55 | 17 |
| 最终 accept | 456 | 516 |
| 最终 review | 58 | 30 |
| 最终 reject | 38 | 6 |

V2.1 新轨道对全部 V1 配对的回归召回为 535/552（96.9%），比诊断性 V2 的 497/552（90.0%）增加 38 对。更有意义的分层结果是：

- 516 个仍被 V2.1 判为 accept 的历史配对：516 个全部由新轨道找回；
- 30 个 review：19 个由新轨道找回，11 个仅由历史 accession 兜底；
- 6 个 reject：均仅由历史 accession 兜底；
- 历史兜底恢复的 accept：0。

因此，“17 个没有被新轨道找回”不等于 17 个漏掉的确认记录。它们全部低于确认阈值。

## 剩余 17 对为何不应强行自动确认

其中 6 对被拒绝：

- `NCPPB 2969` 的 5 个 BioSample 是 Xanthomonas phage，结构化身份字段为空；V1 因噬菌体传播宿主字段出现 `CFBP 2523` 而误连到细菌菌株；
- `NCPPB 3563 / SAMN30096794` 的结构化 strain 是 `Xcp-1`，而目录 Other reference 是 `IIH-Xcp1`，没有完整精确标识符证据。

另外 11 对进入 review：

- `NCPPB 4615 / SAMN25050887` 只在标题中出现 `B100`，而标题明确描述 deletion mutant；
- 其余 10 对依赖 `Arg-1A`、`Arg-2B`、`ARG-3A`、`ARG-6B`、`ARG 4B` 等 donor/local code。它们在 strain 字段中精确出现，但不是正式保藏号，故作为 provisional 候选保留并扩展序列链接，不自动确认。

## V2.1.1 安全门后的主管表

- 确认 BioSample：533 个，覆盖 360 个 NCPPB strain；
- provisional BioSample candidate：40 个 decision rows，涉及 32 个 strain；
- 需要人工审核：92 个 strain、112 个 strain–BioSample pair，其中既包括 provisional 身份，也包括已确认身份但分类名/pathovar 需复核的记录；
- 自动可用于下一步 QC 的 Assembly：262 个 strain；
- 自动可用的 WGS SRA fallback：46 个 strain；
- 49 个 strain 虽有链接序列，但在分类名/pathovar 审核完成前不自动选择；
- 安全门后确认可用的 BioProject 来源：308 个 strain。

此外，`identifier_review_queue.tsv` 单列出 232 条可能有价值但尚未允许自动检索的 identifier。当前目录中 884 行仍名为 *Xanthomonas*，13 行已重分类到其他属，但都保留在 897 行主管表中并标注 scope。

这一步修正了真实的错误选择：NCPPB 2217 不再选择两个 *Staphylococcus aureus* runs，而改选 *Xylophilus ampelinus* 的 ERR3330907；NCPPB 2930 的 *Sphingomonas* Assembly/SRA 仍留在审计证据中，但不会自动进入发育树输入。

## V1、V2 和 V2.1 的关系

V1 不是金标准：它的扁平全文匹配能提高表面召回，但会把 propagation host、衍生株或局部短码当成同一菌株。诊断性 V2 又走向另一个极端：quoted phrase、retmax=100 和遗漏 alias 字段造成真实低召回。V2.1 的优化不是简单取二者并集，而是：

1. 用批量前缀加逐编号完整字符串保证候选召回；
2. 分页并审计 reported/retrieved counts，禁止静默截断；
3. 只在结构化身份字段进行完整边界匹配；
4. 将正式编号、局部代码和标题证据分层；
5. 将身份确认与分类学复核分离；
6. 用 V1 全量配对做回归控制，但不继承 V1 的错误结论。

机器可审计的逐对结果见 `runs/audit/2026-07-10_v2.1.1/v1_regression_recall_audit.tsv`，主管主表见 `runs/audit/2026-07-10_v2.1.1/supervisor_sequence_availability.tsv`。
