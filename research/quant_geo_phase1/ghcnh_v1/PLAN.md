# GHCNh资料版本1：2025年度条件预测实验

2026-10-29，已知2024旧产品的负结果与2025旧产品覆盖失败后制定。先提交本方案、代码与哈希，再建模。不是外部预注册；2025负荷和旧产品部分天气已接触过，但尚无本轮模型表现。2019—2025整个研究期统一采用GHCNh，绝不将新旧天气拼接。2026档案只取属于纽约2025-12-31的UTC边界小时。

这是更换天气资料版本后的新实验，不要求重现旧2024预测。负荷档案、目标变量、五个机场、站点暴露映射、特征定义、模型候选集、2019—2022训练/2023选参及重拟合截止2023、2025完整评价窗口，均延续原研究。按原2023全样本MAE规则重新选参，共13组流程、每组4个候选与1次重拟合。不将2024加入训练，也不根据2025误差调参。

## 数据规则

以NOAA GHCNh 1.1.0文档为准：温度和露点直接为摄氏度；按UTC解析，再按America/New_York日历聚合。相同小时多条观测先均值，然后求日均，每站每变量有效小时仍须至少90%；不插值。对数值冲突的重复时间戳报错。

温度/露点质量码结合来源：313/314/315/322/335/343/344/346只接受1、5；220/221/222/223/347/348只接受1。拒绝其他码（包括小写综合质控标记），未知有值来源直接停止，不能自行解释。有效值限于−100至70摄氏度，露点超过气温0.5度则剔除露点。来源可在同一产品内部改变，逐年逐站保留全部来源/质量码频数，不把来源变化隐藏。

五站以官方目录中的WBAN、WMO和名称对应原机场，同时核验逐行GHCNh ID及坐标；坐标相对目录偏差超过0.1度停止。这是编号/坐标一致性检查，不是完整站史同质性认证。

先报告2019—2024每年、每站、每变量的新旧有效日期数、配对日均温差、绝对差及最大差，再报告各切分覆盖率；旧产品的质量选择与新产品并不完全等价。重叠差异不用于筛选站点或调参。任一切分可用率低于原90%门槛仍停止，不能缩短2025窗口。

## 判据和解释

主比较：2025固定训练90%分位阈值以上日期，HGB B3对B2的MAE。六项筛选标准以及7/14/28日分块区间各2000次全部沿用原方案；14日为主区间。保留全部13组指标、逐日预测、覆盖和来源哈希，无论正负。没有30个高负荷日则不通过筛选。只评价同一区域同日实测天气下的条件预测，不是日前预报、跨地区验证、因果解释或交易回测；不能用2025正结果抹去2024负结果。

## 复现

先保留旧实验及replication_2025下载的档案，再在上级目录执行：

```bash
python -m pip install -r ghcnh_v1/requirements.txt
python -m unittest -v test_quant_geo_phase1.py test_followup.py test_ghcnh.py
python ghcnh_migrate.py download
python ghcnh_migrate.py prepare
python ghcnh_migrate.py verify
python ghcnh_migrate.py analyse
```

官方来源：
- https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly
- https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf
- https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh-station-list.txt

本文件锁定时未声称实验已经执行。执行状态和偏离另行记录，不重写原锁文件。
