# -*- coding: UTF-8 -*-
"""Calibrate the GreenAmpt-Nash-Muskingum model on train data and validate on test data."""

import argparse
import io
import os
import sys
import warnings
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

from core.calibration_workflow import run_calibration_workflow

DEFAULT_DATA_CSV = Path("dataset") / "example_data.csv"
DEFAULT_PARAMS_JSON = Path("params") / "calibrated_params.json"
DEFAULT_OUTPUTS_DIR = Path("outputs")


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def calibrate(
    data_csv: str | os.PathLike | None = None,
    output_json: str | os.PathLike | None = None,
    area: float = 150.0,
    dt: float = 1.0,
    epochs: int = 100,
    pop_size: int = 80,
    train_ratio: float = 2.0 / 3.0,
    seed: int | None = 42,
    figures_dir: str | os.PathLike | None = None,
    save_figures: bool = True,
):
    """Run the full calibration workflow and return the structured result."""
    data_csv = Path(data_csv) if data_csv is not None else DEFAULT_DATA_CSV
    output_json = Path(output_json) if output_json is not None else DEFAULT_PARAMS_JSON
    figures_dir = Path(figures_dir) if figures_dir is not None else DEFAULT_OUTPUTS_DIR

    print_header("GreenAmpt-Nash-Muskingum 参数率定")
    print(f"  数据文件: {data_csv}")
    print(f"  流域面积: {area:.3f} km2")
    print(f"  时间步长: {dt:.3f} h")
    print(f"  WOA 配置: {epochs} 代 x {pop_size} 个体, seed={seed}")

    train_df, test_df, result, written = run_calibration_workflow(
        data_csv=data_csv,
        output_json=output_json,
        figures_dir=figures_dir,
        area=area,
        dt=dt,
        epochs=epochs,
        pop_size=pop_size,
        train_ratio=train_ratio,
        seed=seed,
        save_figures=save_figures,
    )

    print_header("训练/测试划分")
    print(f"  训练集: {len(train_df)} h, 洪峰 {train_df['Observed_Flow_m3s'].max():.2f} m3/s")
    print(f"  测试集: {len(test_df)} h, 洪峰 {test_df['Observed_Flow_m3s'].max():.2f} m3/s")

    train_perf = result.performance["train"]
    test_perf = result.performance["test"]
    print_header("率定完成")
    print(
        f"  训练集: NSE={train_perf['NSE']:.4f}, RMSE={train_perf['RMSE_m3s']:.2f} m3/s, "
        f"PBIAS={train_perf['PBIAS_pct']:.2f}%, 洪峰误差={train_perf['peak_error_pct']:.2f}%"
    )
    print(
        f"  测试集: NSE={test_perf['NSE']:.4f}, RMSE={test_perf['RMSE_m3s']:.2f} m3/s, "
        f"PBIAS={test_perf['PBIAS_pct']:.2f}%, 洪峰误差={test_perf['peak_error_pct']:.2f}%"
    )
    p = result.parameters
    print(
        "  参数: "
        f"Ks={p['Ks']:.3e}, psi={p['suction_head']:.4f}, "
        f"Delta_theta={p['delta_theta']:.4f}, n={p['n']:.4f}, "
        f"k={p['k']:.4f}, K={p['K_musk']:.4f}, x={p['x_musk']:.4f}"
    )
    print(f"  参数 JSON: {written['params_json']}")
    if save_figures:
        print(f"  总览图: {written['summary_figure']}")
        print(f"  训练过程图: {written['training_figure']}")
        print(f"  训练/测试拟合图: {written['fit_figure']}")
    return result


def parse_seed(value: str) -> int | None:
    if value.lower() in {"none", "null", "random"}:
        return None
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="率定 GreenAmpt-Nash-Muskingum 模型参数并绘制诊断图")
    parser.add_argument("data_csv", nargs="?", default=str(DEFAULT_DATA_CSV), help="历史降雨-流量 CSV")
    parser.add_argument("-o", "--output", default=str(DEFAULT_PARAMS_JSON), help="输出参数 JSON")
    parser.add_argument("--figures-dir", default=str(DEFAULT_OUTPUTS_DIR), help="输出图件目录")
    parser.add_argument("-a", "--area", type=float, default=150.0, help="流域面积 km2")
    parser.add_argument("--dt", type=float, default=1.0, help="时间步长 h")
    parser.add_argument("-e", "--epochs", type=int, default=100, help="WOA 代数")
    parser.add_argument("-p", "--population", type=int, default=80, help="WOA 种群大小")
    parser.add_argument("--train-ratio", type=float, default=2.0 / 3.0, help="无 Split 列时按时间顺序划分训练集比例")
    parser.add_argument("--seed", type=parse_seed, default=42, help="随机种子；用 none/random 表示不固定")
    parser.add_argument("--no-plots", action="store_true", help="只保存 JSON，不绘图")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    data_csv = Path(args.data_csv)
    if not data_csv.exists():
        print(f"错误: 找不到数据文件 '{data_csv}'")
        print("请先运行: python generate_example_data.py")
        return 1
    calibrate(
        data_csv=data_csv,
        output_json=args.output,
        area=args.area,
        dt=args.dt,
        epochs=args.epochs,
        pop_size=args.population,
        train_ratio=args.train_ratio,
        seed=args.seed,
        figures_dir=args.figures_dir,
        save_figures=not args.no_plots,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
