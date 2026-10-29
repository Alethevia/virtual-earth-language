# 量化地理实验包 001

**2026-10-29：真实数据建模已完成，原定主假设未通过。新增站点身份后高负荷日误差增加10.07%。详见[结果报告](RESULTS.md)。**

后续：[2024误差分解](DIAGNOSTICS_2024.md)已完成；[2025时间复验](replication_2025/STATUS.md)因旧NOAA天气产品停更、全年可用率仅64.93%而停止，未拟合新模型，不能算作新的性能负结果。原数据产品适合本包2019—2024历史复现；后续已完成独立的[GHCNh资料版本实验](ghcnh_v1/RESULTS.md)：2025可用338天，高负荷误差改善6.35%，但主区间跨零，完整筛选仍未通过。旧数据源停止记录仍保留。

研究纽约州天气空间分布是否为日峰值负荷提供增量解释。请先阅读 [PROTOCOL.md](PROTOCOL.md)。方案使用同日事后天气，不能视为日前可用预测或交易策略。

## 运行

Python 3.11+，在本目录执行：

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m unittest -v test_quant_geo_phase1.py test_followup.py
python quant_geo_phase1.py download
python quant_geo_phase1.py prepare
# 交叉核验官方五分钟与小时负荷的时间标签：
python verify_intervals.py
python quant_geo_phase1.py analyse
```

不需要API密钥。原始数据不会随Git仓库分发；下载器从NYISO和NOAA获取并记录来源URL、时间、字节数和SHA-256。下载/结构/校验失败会报错，不会生成假数据。

## 已执行证据

- [37项离线检查](qa/unit_tests_followup_20261029.txt)通过，其中包含原32项人工夹具检查、误差核算和锁文件/历史数据核验保障。
- 原包中的[13个模型流程人工冒烟检查](qa/artificial_model_smoke.json)仅验证程序流程。
- [官方下载记录](qa/download_20261029.txt)及[来源与哈希清单](qa/raw_download_manifest_20261029.json)：72个NYISO月档案、30个NOAA站点年度请求。
- [真实数据整理审计](qa/data_preparation_20261029.json)：2019–2024年，2,192天完整负荷、2,145天天气完整；五个站点身份通过解析检查。
- [执行状态](execution_status.json)：完成13个真实模型/对照流程；五日原始数据交叉核验支持小时起点标签。
- [真实评价结果](RESULTS.md)：2024年362个可用测试日、33个高负荷日，主假设未通过；包含完整逐日预测及不确定性区间。

`protocol.json`保留原先固定的时间切分、站点、对照与判据。`raw/`、`prepared/`、`results/`是可重新生成的本地数据目录，不提交。官方站点接口若变化，需要显式修复下载器。

## 研究边界

只有一个电力区域，站点与负荷区映射较粗。没有交易价格、持仓或收益计算。即使2024年样本外效果良好，也不能直接证明因果、博士级原创性或可交易优势。本仓库保留首轮真实效果表和负结果，不将其称为原创论文结论。

2024诊断可运行`python diagnose_errors.py`复现，不调用模型拟合。2025已锁定方案、来源审计和停止原因独立保存于`replication_2025/`；其原协议和修订记录均保留，不覆盖2024结果。

GHCNh新实验的运行命令、独立依赖和建模前修订见[方案](ghcnh_v1/PLAN.md)。本轮43项离线检查通过；旧实验的37项检查记录保留作为历史证据。
