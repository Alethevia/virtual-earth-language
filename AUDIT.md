# 运行与真实性审查 — 2026-10-29

## 修复网页构建，新增量化地理研究目录

修复Cesium鼠标事件类型；安装/构建时从锁定依赖复制资源，移除提交的生成副本和过期源码改写脚本。基础依赖与重型研究依赖分离，CI不再吞安装错误。README撤下不可复现的对比百分比，说明确定性符号编码示例。新增research/quant_geo_phase1，保留原锁定方案及研究代码。

## 本次执行证据

原模拟2项测试通过、最小例程通过；Web生产构建通过。地理研究30项离线测试通过；102份官方文件下载解析成功，得到2,192天完整负荷和2,145天天气完整记录。

```text
python -m pytest tests -q
python experiments/minimal_run.py
cd web && npm ci && npm run build
cd ../research/quant_geo_phase1
python -m unittest -v test_quant_geo_phase1.py
python quant_geo_phase1.py download
python quant_geo_phase1.py prepare
```

Python检查使用Linux/Python 3.12。测试结果是本次本地执行记录，不代表GitHub Actions已通过，也不是独立认证。

## 仍未验证的范围

地理实证模型拟合0次；尚需人工确认NYISO时间区间标签惯例。代码测试和数据整理不能证明论文创新或预测优势。更大语言模型实验、全球尺度地理及Web交互未全面验证。

删除仅针对已确认失效、重复说明或可再生成产物。源码、必要资产和不同版本保留；更改可从Git提交历史恢复。
