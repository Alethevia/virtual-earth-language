# 量化地理实验包 001

**2026-10-29：102份官方文件已下载并通过解析；尚未拟合真实数据模型，尚无实证预测结果。**

研究纽约州天气空间分布是否为日峰值负荷提供增量解释。请先阅读 [PROTOCOL.md](PROTOCOL.md)。方案使用同日事后天气，不能视为日前可用预测或交易策略。

## 运行

Python 3.11+，在本目录执行：

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m unittest -v test_quant_geo_phase1.py
python quant_geo_phase1.py download
python quant_geo_phase1.py prepare
# 先人工核验 NYISO 负荷区间起点/终点标签，再进行模型解释：
python quant_geo_phase1.py analyse
```

不需要API密钥。原始数据不会随Git仓库分发；下载器从NYISO和NOAA获取并记录来源URL、时间、字节数和SHA-256。下载/结构/校验失败会报错，不会生成假数据。

## 已执行证据

- [30项离线测试](qa/unit_tests_20261029.txt)通过，测试输入是人工夹具。
- 原包中的[13个模型流程人工冒烟检查](qa/artificial_model_smoke.json)仅验证程序流程。
- [官方下载记录](qa/download_20261029.txt)及[来源与哈希清单](qa/raw_download_manifest_20261029.json)：72个NYISO月档案、30个NOAA站点年度请求。
- [真实数据整理审计](qa/data_preparation_20261029.json)：2019–2024年，2,192天完整负荷、2,145天天气完整；五个站点身份通过解析检查。
- [执行状态](execution_status.json)：真实模型拟合0次。NYISO区间标签惯例仍需人工核验，因此不宣称端到端实证验证完成。

`protocol.json`保留原先固定的时间切分、站点、对照与判据。`raw/`、`prepared/`、`results/`是可重新生成的本地数据目录，不提交。官方站点接口若变化，需要显式修复下载器。

## 研究边界

只有一个电力区域，站点与负荷区映射较粗。没有交易价格、持仓或收益计算。即使2024年样本外效果良好，也不能直接证明因果、博士级原创性或可交易优势。本仓库不包含真实模型效果表或论文结论。
