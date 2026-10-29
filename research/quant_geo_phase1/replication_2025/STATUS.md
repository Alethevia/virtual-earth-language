# 2025时间复验：数据覆盖不合格，未建模

**2026-10-29：停止在数据门槛。没有2025模型预测、性能结果或假设检验结论。** 这次失败是固定数据源不能覆盖完整年份，不是科学假设再次失败。

## 实际执行与证据

方案及代码先提交于[03d970d](https://github.com/Alethevia/virtual-earth-language/commit/03d970db40ad3d7ca00a5d5adca91286efc0cf67)，随后本工作流才请求2025完整年度文件。不是正式外部预注册；旧年度NOAA文件按原设计包含下一年UTC边界小时，不能声称从未接触任何2025观测。

取得119份数据文件：原102份字节哈希保持不变，另增加12份负荷月档案及5份天气年度文件。负荷全年365天完整，但五站天气共同完整只有237天，可用率**64.93%**，未达到原样保留的90%门槛。五个天气响应的最后UTC时间均为`2025-08-27T04:59:00`，9—12月均无数据。

| 检查 | 实际结果 |
|---|---|
| 固定年度窗口 | 2025-01-01—2025-12-31，未缩短 |
| 旧102份文件SHA-256 | 全部一致 |
| 2019—2024已准备数据数值、标签、缺失位置 | 全部一致，绝对容差1e-8 |
| 五站身份 | 按原ID和名称核验通过 |
| 小时标签数值核验 | 原5日＋新增2025年3日，共8日通过 |
| 2025负荷完整日 | 365/365 |
| 2025天气与模型输入完整日 | 237/365，低于90% |
| 新年度模型拟合 / 新超参数搜索 | 0 / 0 |
| 2024模型预测重现门槛 | 未执行：更早的数据覆盖门槛已阻止拟合 |
| 科学筛选通过与否 | 未评价，不能记为负结果 |

准备阶段还发现一个实现细节：新年份完全缺测的日期让天气小时数列从整数存储变为浮点存储，最初的DataFrame检查误把类型变化当成历史数据变化。[实现修订01](amendment_01.json)只允许这一存储类型差异；仍严格检查原数值、索引、列和缺失位置，并增加防止放过真实数值变化的测试。原锁文件和原代码哈希保留；模型、质量门槛、年份和参数均未改变。

## 上游原因

NOAA官方已说明ISD/Global Hourly被GHCNh取代，旧产品在2025年8月停止更新。官方不同通知对结束日期的表述略有差别；本实验以保存的五个响应的精确时间范围为准。

- [NOAA/NESDIS服务迁移通知，2026-06-23](https://www.nesdis.noaa.gov/news/service-location-change-integrated-surface-data-global-hourly)：旧ISD不再更新，建议迁移GHCNh。
- [NCEI旧Global Hourly产品目录](https://www.ncei.noaa.gov/access/search/datasets/global-hourly/)：标明已被新版本取代，目录记录终止于2025年8月。
- [NCEI GHCNh产品说明](https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly)：新产品整合来源、站点标识和质量控制，不能假定与旧数据字段等价。
- [GHCNh 1.1.0技术文档，2026-03-10](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf)。

这些来源解释数据停更，不提供本项目的模型性能证据。

## 接下来的迁移边界

另立GHCNh数据版本与方案后再进行复验，保留本次未完成记录。需要先核验五个机场的官方站点映射、位置与历次变更；依据GHCNh文档实现温度、露点、原始来源及新质量标志解析；验证时区、重复观测和日覆盖规则。

使用2019—2024重叠期量化两产品的观测差异、有效小时差异和缺失变化，再决定可比较的固定资料版本。不能把新产品简单拼接在2025年8月之后，也不能把新质量码直接当作旧`1/5`标志。若需重算训练资料，必须如实说明这已是新数据版本的实验，不能继续声称精确复现旧模型输入。

新实验仍应在查看新模型表现前锁定处理流程和完整2025评价窗口，报告与旧实验的差异；不能为了得到结果改为只测1—8月。本记录保留该次停止时的状态。后续已经另立方案完成[GHCNh资料版本实验](../ghcnh_v1/RESULTS.md)，不把新实验结果倒填到本次旧资料复验中。

## 可复核文件

- [全年逐日覆盖](qa/daily_coverage.csv)、[逐月覆盖](qa/monthly_coverage.csv)、[机器可读审计](qa/data_audit.json)
- [全部文件来源与哈希](qa/download_manifest.json)、[整理审计](qa/preparation_audit.json)、[整理来源记录](qa/preparation_provenance.json)
- [八日时间标签核验](qa/interval_convention_20261029.json)
- [运行被覆盖门槛阻止的日志](qa/analysis_stopped.txt)、[执行状态](execution_status.json)

运行`python audit_replication_data.py`重建覆盖审计；运行`python replicate_2025.py analyse`应在拟合之前报出覆盖不足，而不是产出部分年度成绩。
