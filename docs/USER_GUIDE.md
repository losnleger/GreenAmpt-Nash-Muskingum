# GreenAmpt-Nash-Muskingum 洪水预报模型用户手册

## 1. 当前工作流

本项目实现集总式洪水预报链路：

```text
Rainfall -> Green-Ampt excess rainfall -> Nash unit hydrograph -> Muskingum routing -> discharge
```

当前推荐流程是：

1. 准备带实测流量的历史降雨-流量 CSV。
2. 按 `Split=train/test` 或时间顺序比例拆分训练集和测试集。
3. 仅在训练集上用 WOA 率定 7 个参数。
4. 用同一组参数分别评估训练集和测试集拟合程度。
5. 保存参数 JSON、训练过程图、训练/测试拟合图和总览图。
6. 用率定参数驱动独立预报降雨 CSV。

`calibrate.py` 是正式率定入口；`train.py` 只是兼容旧习惯的“一键演示”薄封装，不再单独维护一份重复逻辑。

## 2. 环境要求

```bash
python -m pip install -e .
```

也可以只安装运行依赖：

```bash
python -m pip install -r requirements.txt
```

## 3. 生成示例数据

```bash
python generate_example_data.py
```

会生成：

- `dataset/example_data.csv`：120 h 历史降雨-流量数据，含 `Split` 列，前 72 h 为训练集，后 48 h 为测试集。
- `dataset/example_forecast.csv`：默认预报降雨文件，供 `forecast.py` 直接运行。

## 4. 率定与验证

推荐命令：

```bash
python calibrate.py dataset/example_data.csv -o params/calibrated_params.json --figures-dir outputs -a 150 --dt 1 -e 100 -p 80 --seed 42
```

常用参数：

| 参数 | 说明 |
|---|---|
| `data_csv` | 历史降雨-流量 CSV |
| `-o, --output` | 输出参数 JSON |
| `--figures-dir` | 输出图件目录 |
| `-a, --area` | 流域面积，单位 km2 |
| `--dt` | 时间步长，单位 h |
| `-e, --epochs` | WOA 迭代代数 |
| `-p, --population` | WOA 种群规模 |
| `--train-ratio` | 无 `Split` 列时，按时间顺序划分训练集比例 |
| `--seed` | 随机种子；可用 `none`/`random` 不固定 |
| `--no-plots` | 只保存 JSON，不绘图 |

输出文件：

- `params/calibrated_params.json`：参数、训练/测试指标、参数边界、优化配置、训练历史、逐时模拟序列。
- `outputs/train_result.png`：降雨-流量总览图，含训练期、测试期、散点拟合和参数表。
- `outputs/calibration_training_curve.png`：率定过程曲线，显示最优 `1 - NSE` 和训练 NSE 随迭代变化。
- `outputs/train_test_fit.png`：训练集与测试集过程线拟合和散点拟合。

## 5. 输入数据格式

率定 CSV 至少需要：

| 列名 | 单位 | 说明 |
|---|---|---|
| `Time_h` | h | 可选；缺失时自动按行号生成 |
| `Rainfall_mmh` | mm/h | 逐时降雨强度 |
| `Observed_Flow_m3s` | m3/s | 逐时实测流量 |
| `Split` | - | 可选；填 `train` 或 `test` |

如果没有 `Split` 列，程序按时间顺序用 `--train-ratio` 划分。水文时间序列不建议随机打乱切分。

## 6. 预报

先完成率定，再运行：

```bash
python forecast.py dataset/example_forecast.csv -p params/calibrated_params.json -o outputs/forecast_result.csv --plot outputs/forecast_result.png
```

预报 CSV 支持：

- `Forecast_Rainfall_mmh`
- 或 `Rainfall_mmh`

输出：

- `outputs/forecast_result.csv`
- `outputs/forecast_result.png`

## 7. 参数说明

| 子模型 | 参数 | 单位 | 当前搜索范围 |
|---|---|---|---|
| Green-Ampt | `Ks` | m/s | `1e-8` 到 `1e-5` |
| Green-Ampt | `suction_head` | m | `0.005` 到 `0.5` |
| Green-Ampt | `delta_theta` | - | `0.1` 到 `0.5` |
| Nash | `n` | - | `2.0` 到 `5.0` |
| Nash | `k` | h | `1.0` 到 `3.5` |
| Muskingum | `K_musk` | h | `0.5` 到 `10.0` |
| Muskingum | `x_musk` | - | `0.0` 到 `0.5` |

这些范围是工程筛选范围。真实项目应根据土壤、汇流时间、河道传播时间和历史洪水资料收紧边界。
Muskingum 参数还必须满足显式稳定性条件 `2*K*x <= dt <= 2*K*(1-x)`；不满足时会被拒绝或在率定中惩罚，不再静默改写参数。

## 8. 指标解读

JSON 和图中包含：

- `NSE`：纳什效率系数，越接近 1 越好。
- `RMSE_m3s`：均方根误差。
- `MAE_m3s`：平均绝对误差。
- `PBIAS_pct`：体积偏差百分比，正值表示总体低估模拟流量。
- `correlation`：线性相关系数。
- `peak_error_pct`：洪峰相对误差。

注意：训练集表现好只说明参数能拟合率定期；测试集表现才是泛化能力的主要证据。测试集 NSE 较差时，不应把模型作为业务预报模型使用。

本仓库自带的 `dataset/example_data.csv` 是由模型生成并加入噪声的合成示例数据，只能用于演示、冒烟测试和教学，不构成真实流域专业验证。

## 9. Agent Skill

仓库根目录的 `AGENTS.md` 和 `skills/greenampt-nash-muskingum/SKILL.md` 为通用 agent 提供固定工作流。任何 agent 都应先读取这些文件，再执行安装、率定、预报和验证命令。

## 10. 技术参考

- Green, W.H. & Ampt, G.A. (1911). Studies on soil physics: I. The flow of air and water through soils. Journal of Agricultural Science.
- Nash, J.E. (1957). The form of the instantaneous unit hydrograph. IAHS Publication.
- McCarthy, G.T. (1938). The unit hydrograph and flood routing. US Army Corps of Engineers.
- Mirjalili, S. & Lewis, A. (2016). The Whale Optimization Algorithm. Advances in Engineering Software.
