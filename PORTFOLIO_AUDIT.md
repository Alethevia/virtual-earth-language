# 公开仓库修复记录 — 2026-10-29

本记录列出本次实际修改和验证范围。测试通过不等于真实盈利、产品可商用或论文贡献成立。每个仓库AUDIT.md记录具体命令与限制。

|仓库|主要修复|本地验证|
|---|---|---|
|[AI_Agents](https://github.com/Alethevia/AI_Agents)|恢复默认分支实现，修正事件顺序和成交记账|3项回归测试通过；完整人工行情示例完成，16次成交、8笔已平仓交易并生成图表。|
|[AI_Agents_Forex](https://github.com/Alethevia/AI_Agents_Forex)|离线模式与MT5分离，显式标记人工行情|6项离线依赖测试通过；--years 0.03人工行情流程完成、生成报告，交易数为0，因此此次冒烟不验证成交逻辑。|
|[Alpha-Research](https://github.com/Alethevia/Alpha-Research)|修复安装元数据，撤下未经复现的收益结论|281项现有测试通过；可编辑安装及alpha-research --help通过。|
|[Alpha-Research_2](https://github.com/Alethevia/Alpha-Research_2)|移除硬编码历史胜率，修复日期索引|2项离线测试通过：数值声明撤下检查，以及600行人工OHLCV指标、形态、预测流程。|
|[MetaLearning_MT5](https://github.com/Alethevia/MetaLearning_MT5)|规范MQL5文件名并纠正能力描述|已核对源码入口和README；未执行MQL5编译。|
|[Miaomiaokaiheiwu](https://github.com/Alethevia/Miaomiaokaiheiwu)|恢复前后端构建，区分演示数据和真实服务|Next.js静态导出构建通过（显式演示环境）；Prisma客户端生成和后端TypeScript编译通过。|
|[Niubility](https://github.com/Alethevia/Niubility)|补齐训练依赖并修复随机种子|7项测试通过；CPU执行120步SAC短训练，成功保存checkpoint并推理一次。|
|[Stock_Deepseeker](https://github.com/Alethevia/Stock_Deepseeker)|修复两套回测入口的会计与成交错误|205项测试通过，包括新增会计与CLI/v2成交回归；确定性人工行情示例有2次成交、0次拒单。|
|[Stock_Trading_Robot_RAC](https://github.com/Alethevia/Stock_Trading_Robot_RAC)|修复导出类型和配置读取，收敛说明|1项离线回归测试通过。|
|[virtual-earth-language](https://github.com/Alethevia/virtual-earth-language)|修复网页构建，新增量化地理研究目录|原模拟2项测试通过、最小例程通过；Web生产构建通过。地理研究32项离线检查通过；真实建模及2024年留出评价完成，原定高负荷主假设未通过，完整负结果可复查。|

[新增量化地理研究目录](research/quant_geo_phase1/README.md)。真实数据首轮建模完成；[结果报告](research/quant_geo_phase1/RESULTS.md)保留全部对照和负结果。
