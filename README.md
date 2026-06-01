# GreenAmpt-Nash-Muskingum

Languages: [简体中文](#简体中文) | [English](#english)

## 简体中文

GreenAmpt-Nash-Muskingum 是一个用于**集总式降雨径流模拟与洪水演算**的 Python 教学科研原型：

```text
降雨 -> Green-Ampt 产流 / 净雨 -> Nash 单位线汇流 -> Muskingum 河道演算 -> 流量过程线
```

本仓库适用于教学、科研原型验证和二次开发，不是经过专业认证的业务洪水预报系统。

### 包含内容

- Green-Ampt 入渗 / 产流计算。
- Nash 单位线汇流。
- 带显式稳定性检查的 Muskingum 河道演算。
- 基于 `mealpy` 的 WOA 参数率定。
- 时间顺序或显式 `Split=train/test` 的训练 / 测试划分。
- NSE、RMSE、MAE、PBIAS、相关系数和洪峰误差指标。
- JSON 参数输出和诊断图件。
- 平台无关的智能体 skill：`skills/greenampt-nash-muskingum/SKILL.md`。

### 安装

克隆仓库后安装：

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

如果只想直接运行脚本，也可以安装依赖：

```bash
python -m pip install -r requirements.txt
```

建议使用 Python 3.11 或更新版本。

### 快速开始

生成合成演示数据：

```bash
python generate_example_data.py
```

在训练期率定参数，并在测试期评估：

```bash
python calibrate.py dataset/example_data.csv -o params/calibrated_params.json --figures-dir outputs -a 150 --dt 1 -e 100 -p 80 --seed 42
```

使用降雨 CSV 进行预报：

```bash
python forecast.py dataset/example_forecast.csv -p params/calibrated_params.json -o outputs/forecast_result.csv --plot outputs/forecast_result.png
```

安装后也可以使用命令行入口：

```bash
gnm-generate-example
gnm-calibrate dataset/example_data.csv
gnm-forecast dataset/example_forecast.csv
```

### 输入数据

率定 CSV 字段：

| 字段 | 单位 | 是否必需 | 说明 |
|---|---:|---:|---|
| `Time_h` | h | 否 | 从事件开始计的时间。缺失时使用行号。 |
| `Rainfall_mmh` | mm/h | 是 | 每个时间步的降雨强度。 |
| `Observed_Flow_m3s` | m3/s | 是 | 实测流量。 |
| `Split` | - | 否 | `train` 或 `test`。缺失时使用时间顺序 `--train-ratio` 划分。 |

预报 CSV 字段：

| 字段 | 单位 | 是否必需 | 说明 |
|---|---:|---:|---|
| `Forecast_Rainfall_mmh` | mm/h | 是 | 推荐的预报降雨强度字段。 |
| `Rainfall_mmh` | mm/h | 替代 | 当 `Forecast_Rainfall_mmh` 缺失时可使用。 |

程序内部会把降雨强度从 mm/h 转换为 m/s。累计雨量按 `sum(intensity_mmh) * dt_h` 计算，因此支持非 1 小时时间步长。

### 参数

| 子模型 | 参数 | 单位 | 默认搜索范围 |
|---|---|---:|---|
| Green-Ampt | `Ks` | m/s | `1e-8` 到 `1e-5` |
| Green-Ampt | `suction_head` | m | `0.005` 到 `0.5` |
| Green-Ampt | `delta_theta` | - | `0.1` 到 `0.5` |
| Nash | `n` | - | `2.0` 到 `5.0` |
| Nash | `k` | h | `1.0` 到 `3.5` |
| Muskingum | `K_musk` | h | `0.5` 到 `10.0` |
| Muskingum | `x_musk` | - | `0.0` 到 `0.5` |

Muskingum 参数只有在满足 `2*K*x <= dt <= 2*K*(1-x)` 时才会被接受。不稳定组合会在直接模拟时被拒绝，在率定中被惩罚。

### 验证边界

仓库自带的 `dataset/example_data.csv` 是由模型生成并加入噪声的合成数据。它适合冒烟测试、可复现流程演示和教学，不代表真实流域预测能力。

用于真实流域前，应至少完成：

- 替换为来源可追溯的实测降雨和流量。
- 根据土壤、流域和河道证据设置参数范围。
- 保持率定期和验证期分离。
- 报告训练期和测试期指标，并明确限制。
- 不要仅凭本仓库用于人员撤离、水库调度、监管审批等安全关键决策。

### 智能体 Skill

智能体应优先读取：

```text
AGENTS.md
skills/greenampt-nash-muskingum/SKILL.md
```

该 skill 提供固定的安装、率定、预报、冒烟测试和结果解释流程。它是普通 Markdown，可供任何智能体或人工用户使用。

### 测试

运行：

```bash
python -m compileall .
python -m unittest discover -s tests
python skills/greenampt-nash-muskingum/scripts/smoke_check.py --epochs 2 --population 6
```

冒烟测试仅使用合成演示数据。

### 参考文献

- Green, W.H. and Ampt, G.A. (1911). Studies on soil physics: I. The flow of air and water through soils. Journal of Agricultural Science.
- Nash, J.E. (1957). The form of the instantaneous unit hydrograph. IAHS Publication.
- McCarthy, G.T. (1938). The unit hydrograph and flood routing. US Army Corps of Engineers.
- Mirjalili, S. and Lewis, A. (2016). The Whale Optimization Algorithm. Advances in Engineering Software.

### 许可证

MIT License. See `LICENSE`.

## English

A Python research prototype for lumped rainfall-runoff simulation and flood routing:

```text
rainfall -> Green-Ampt excess rainfall -> Nash unit hydrograph -> Muskingum routing -> discharge
```

This repository is intended for teaching, research prototyping, and secondary development. It is not a professionally validated operational flood forecasting system.

## What Is Included

- Green-Ampt infiltration/excess-rainfall calculation.
- Nash unit hydrograph runoff concentration.
- Muskingum channel routing with explicit stability checks.
- WOA-based parameter calibration using `mealpy`.
- Chronological or explicit train/test split.
- NSE, RMSE, MAE, PBIAS, correlation, and peak-error metrics.
- Diagnostic figures and JSON outputs.
- A platform-neutral agent skill in `skills/greenampt-nash-muskingum/SKILL.md`.

## Installation

Clone the repository and install the package:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

For script-only use without installing the package:

```bash
python -m pip install -r requirements.txt
```

Python 3.11 or newer is recommended.

## Quick Start

Generate synthetic demonstration data:

```bash
python generate_example_data.py
```

Calibrate parameters on the training period and evaluate the test period:

```bash
python calibrate.py dataset/example_data.csv -o params/calibrated_params.json --figures-dir outputs -a 150 --dt 1 -e 100 -p 80 --seed 42
```

Run a forecast from a rainfall CSV:

```bash
python forecast.py dataset/example_forecast.csv -p params/calibrated_params.json -o outputs/forecast_result.csv --plot outputs/forecast_result.png
```

Installed console commands are also available:

```bash
gnm-generate-example
gnm-calibrate dataset/example_data.csv
gnm-forecast dataset/example_forecast.csv
```

## Input Data

Calibration CSV columns:

| Column | Unit | Required | Meaning |
|---|---:|---:|---|
| `Time_h` | h | no | Time from the start of the event. Row index is used if omitted. |
| `Rainfall_mmh` | mm/h | yes | Rainfall intensity per time step. |
| `Observed_Flow_m3s` | m3/s | yes | Observed discharge. |
| `Split` | - | no | Use `train` or `test` labels. If omitted, chronological `--train-ratio` is used. |

Forecast CSV columns:

| Column | Unit | Required | Meaning |
|---|---:|---:|---|
| `Forecast_Rainfall_mmh` | mm/h | yes | Forecast rainfall intensity. |
| `Rainfall_mmh` | mm/h | alternative | Accepted when `Forecast_Rainfall_mmh` is absent. |

Rainfall intensity is converted internally from mm/h to m/s. Total rainfall depth is computed as `sum(intensity_mmh) * dt_h`, so non-1-hour time steps are supported.

## Parameters

| Submodel | Parameter | Unit | Default search range |
|---|---|---:|---|
| Green-Ampt | `Ks` | m/s | `1e-8` to `1e-5` |
| Green-Ampt | `suction_head` | m | `0.005` to `0.5` |
| Green-Ampt | `delta_theta` | - | `0.1` to `0.5` |
| Nash | `n` | - | `2.0` to `5.0` |
| Nash | `k` | h | `1.0` to `3.5` |
| Muskingum | `K_musk` | h | `0.5` to `10.0` |
| Muskingum | `x_musk` | - | `0.0` to `0.5` |

The Muskingum coefficients are only accepted when `2*K*x <= dt <= 2*K*(1-x)`. Invalid combinations are rejected during direct simulation and penalized during calibration.

## Validation Boundary

The included `dataset/example_data.csv` is synthetic data generated from the model plus noise. It is useful for smoke tests, reproducibility checks, workflow demonstrations, and teaching. It is not evidence of real-basin predictive skill.

Before using this project for a real watershed:

- Replace the synthetic data with traceable observed rainfall and discharge.
- Set parameter bounds from soil, watershed, and channel evidence.
- Keep train/test or calibration/validation periods separate.
- Report validation metrics and limitations honestly.
- Do not use this repository alone for safety-critical evacuation, dam operation, or regulatory decisions.

## Agent Skill

Agents should start with:

```text
AGENTS.md
skills/greenampt-nash-muskingum/SKILL.md
```

The skill gives fixed commands for setup, calibration, forecasting, smoke checks, and result interpretation. It is plain Markdown and can be used by any agent or by humans.

## Tests

Run:

```bash
python -m compileall .
python -m unittest discover -s tests
python skills/greenampt-nash-muskingum/scripts/smoke_check.py --epochs 2 --population 6
```

The smoke check uses synthetic demonstration data only.

## References

- Green, W.H. and Ampt, G.A. (1911). Studies on soil physics: I. The flow of air and water through soils. Journal of Agricultural Science.
- Nash, J.E. (1957). The form of the instantaneous unit hydrograph. IAHS Publication.
- McCarthy, G.T. (1938). The unit hydrograph and flood routing. US Army Corps of Engineers.
- Mirjalili, S. and Lewis, A. (2016). The Whale Optimization Algorithm. Advances in Engineering Software.

## License

MIT License. See `LICENSE`.
