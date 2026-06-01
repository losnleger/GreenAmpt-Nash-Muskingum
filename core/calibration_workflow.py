# -*- coding: UTF-8 -*-
"""Shared calibration workflow for the GreenAmpt-Nash-Muskingum model.

This module keeps the scientific model equations in the original core file and
centralizes the engineering workflow around them: data splitting, WOA
calibration, metrics, and diagnostic plotting.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from mealpy import FloatVar
from mealpy.swarm_based import WOA

from core.model import GreenAmpt, MuskingumRouting, NashHydrographCalculator, is_muskingum_stable

PARAMETER_NAMES = (
    "Ks",
    "suction_head",
    "delta_theta",
    "n",
    "k",
    "K_musk",
    "x_musk",
)

DEFAULT_PARAMETER_BOUNDS = {
    "Ks": (1e-8, 1e-5),
    "suction_head": (0.005, 0.5),
    "delta_theta": (0.1, 0.5),
    "n": (2.0, 5.0),
    "k": (1.0, 3.5),
    "K_musk": (0.5, 10.0),
    "x_musk": (0.0, 0.5),
}

REQUIRED_COLUMNS = ("Rainfall_mmh", "Observed_Flow_m3s")


logging.getLogger("mealpy").setLevel(logging.ERROR)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130


@dataclass
class CalibrationResult:
    model: str
    area_km2: float
    dt_h: float
    parameters: dict[str, float]
    performance: dict[str, dict[str, float | int | None]]
    calibration_config: dict[str, Any]
    history: dict[str, list[float | int]]
    series: dict[str, dict[str, list[float]]]


def validate_calibration_frame(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required calibration columns: {', '.join(missing)}")
    if len(df) < 4:
        raise ValueError("Calibration data must contain at least 4 rows.")


def split_calibration_data(
    df: pd.DataFrame,
    train_ratio: float = 2.0 / 3.0,
    split_column: str = "Split",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return train/test frames using explicit labels or chronological ratio."""
    validate_calibration_frame(df)
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0 and 1.")

    data = df.copy()
    if "Time_h" not in data.columns:
        data["Time_h"] = np.arange(len(data), dtype=float)

    if split_column in data.columns:
        split = data[split_column].astype(str).str.strip().str.lower()
        train = data[split == "train"].copy()
        test = data[split == "test"].copy()
        if len(train) > 0 and len(test) > 0:
            return train.reset_index(drop=True), test.reset_index(drop=True)

    n_train = int(round(len(data) * train_ratio))
    n_train = min(max(n_train, 1), len(data) - 1)
    train = data.iloc[:n_train].copy()
    test = data.iloc[n_train:].copy()
    train[split_column] = "train"
    test[split_column] = "test"
    return train.reset_index(drop=True), test.reset_index(drop=True)


def rainfall_to_mps(rainfall_mmh: np.ndarray | pd.Series) -> np.ndarray:
    return np.asarray(rainfall_mmh, dtype=float) / 1000.0 / 3600.0


def simulate(params: list[float] | tuple[float, ...] | np.ndarray, rain_mps: np.ndarray, area: float, dt: float) -> np.ndarray:
    """Run Green-Ampt, Nash unit hydrograph, and Muskingum routing."""
    Ks, suction_head, delta_theta, n, k, K_musk, x_musk = [float(v) for v in params]
    ga = GreenAmpt(Ks, suction_head, delta_theta, delta_t=dt * 3600.0)
    net_rain_mm = np.array([ga.calculate_runoff(float(r)) for r in rain_mps], dtype=float)
    nash = NashHydrographCalculator(n=n, k=k, area_km2=area, dt=dt)
    muskingum = MuskingumRouting(K=K_musk, x=x_musk, dt=dt)
    return np.asarray(muskingum.route_flow(nash.convolve_hydrograph(net_rain_mm)), dtype=float)


def nse(obs: np.ndarray, sim: np.ndarray) -> float:
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    ss_tot = float(np.sum((obs - np.mean(obs)) ** 2))
    if ss_tot <= 1e-12:
        return float("nan")
    ss_res = float(np.sum((obs - sim) ** 2))
    return 1.0 - ss_res / ss_tot


def evaluate_simulation(obs: np.ndarray, sim: np.ndarray) -> dict[str, float | int | None]:
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    n_cmp = min(len(obs), len(sim))
    if n_cmp == 0:
        raise ValueError("Cannot evaluate empty observed/simulated series.")
    obs = obs[:n_cmp]
    sim = sim[:n_cmp]
    residual = obs - sim
    obs_sum = float(np.sum(obs))
    obs_peak = float(np.max(obs))
    sim_peak = float(np.max(sim))
    if n_cmp > 1 and float(np.std(obs)) > 1e-12 and float(np.std(sim)) > 1e-12:
        corr = float(np.corrcoef(obs, sim)[0, 1])
    else:
        corr = None
    return {
        "NSE": round(float(nse(obs, sim)), 4),
        "RMSE_m3s": round(float(np.sqrt(np.mean(residual**2))), 3),
        "MAE_m3s": round(float(np.mean(np.abs(residual))), 3),
        "PBIAS_pct": round(float(100.0 * np.sum(residual) / obs_sum), 3) if abs(obs_sum) > 1e-12 else None,
        "correlation": round(corr, 4) if corr is not None else None,
        "peak_observed": obs_peak,
        "peak_simulated": sim_peak,
        "peak_error_pct": round(float(abs(sim_peak - obs_peak) / obs_peak * 100.0), 3) if obs_peak > 1e-12 else None,
        "hours": int(n_cmp),
    }


def _fitness_from_nse(params: np.ndarray, rain_mps: np.ndarray, obs_flow: np.ndarray, area: float, dt: float) -> float:
    if not _parameters_are_valid(params, dt=dt):
        return 10.0
    try:
        sim = simulate(params, rain_mps, area, dt)
        n_cmp = min(len(obs_flow), len(sim))
        score = nse(obs_flow[:n_cmp], sim[:n_cmp])
        if not np.isfinite(score):
            return 10.0
        return float(1.0 - score)
    except Exception:
        return 10.0


def _parameters_are_valid(params: np.ndarray | list[float] | tuple[float, ...], dt: float | None = None) -> bool:
    values = [float(v) for v in params]
    if len(values) != len(PARAMETER_NAMES):
        return False
    for value, name in zip(values, PARAMETER_NAMES):
        lb, ub = DEFAULT_PARAMETER_BOUNDS[name]
        if value < lb or value > ub:
            return False
    if dt is not None and not is_muskingum_stable(values[5], values[6], dt):
        return False
    return True


def _make_bounds() -> list[FloatVar]:
    return [
        FloatVar(lb=DEFAULT_PARAMETER_BOUNDS[name][0], ub=DEFAULT_PARAMETER_BOUNDS[name][1], name=name)
        for name in PARAMETER_NAMES
    ]


def _extract_history(opt_model: Any) -> dict[str, list[float | int]]:
    best_fitness: list[float] = []
    history = getattr(opt_model, "history", None)
    candidates = (
        getattr(history, "list_global_best", None),
        getattr(history, "list_current_best", None),
        getattr(history, "list_global_best_fit", None),
        getattr(history, "list_current_best_fit", None),
    )
    for candidate in candidates:
        if not candidate:
            continue
        values: list[float] = []
        for item in candidate:
            fitness = item
            target = getattr(item, "target", None)
            if target is not None:
                fitness = getattr(target, "fitness", target)
            try:
                values.append(float(fitness))
            except (TypeError, ValueError):
                values = []
                break
        if values:
            best_fitness = values
            break
    if not best_fitness:
        try:
            best_fitness = [float(opt_model.g_best.target.fitness)]
        except Exception:
            best_fitness = []
    epoch = list(range(1, len(best_fitness) + 1))
    return {
        "epoch": epoch,
        "best_fitness": [round(float(v), 6) for v in best_fitness],
        "best_nse": [round(float(1.0 - v), 6) for v in best_fitness],
    }


def calibrate_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    area: float = 150.0,
    dt: float = 1.0,
    epochs: int = 100,
    pop_size: int = 80,
    seed: int | None = 42,
) -> CalibrationResult:
    if area <= 0:
        raise ValueError("area must be positive.")
    if dt <= 0:
        raise ValueError("dt must be positive.")
    if epochs <= 0 or pop_size <= 0:
        raise ValueError("epochs and pop_size must be positive.")

    train_rain = rainfall_to_mps(train_df["Rainfall_mmh"])
    test_rain = rainfall_to_mps(test_df["Rainfall_mmh"])
    train_obs = np.asarray(train_df["Observed_Flow_m3s"], dtype=float)
    test_obs = np.asarray(test_df["Observed_Flow_m3s"], dtype=float)

    def objective(solution):
        return _fitness_from_nse(np.asarray(solution, dtype=float), train_rain, train_obs, area, dt)

    problem = {
        "obj_func": objective,
        "bounds": _make_bounds(),
        "minmax": "min",
        "log_to": None,
    }
    opt_model = WOA.OriginalWOA(epoch=epochs, pop_size=pop_size)
    if seed is not None:
        np.random.seed(seed)
    try:
        opt_model.solve(problem, seed=seed)
    except TypeError:
        opt_model.solve(problem)

    best = np.asarray(opt_model.g_best.solution, dtype=float)
    sim_train = simulate(best, train_rain, area, dt)
    sim_test = simulate(best, test_rain, area, dt)
    n_train = min(len(train_obs), len(sim_train))
    n_test = min(len(test_obs), len(sim_test))

    return CalibrationResult(
        model="GreenAmpt-Nash-Muskingum",
        area_km2=float(area),
        dt_h=float(dt),
        parameters={name: float(value) for name, value in zip(PARAMETER_NAMES, best)},
        performance={
            "train": evaluate_simulation(train_obs, sim_train),
            "test": evaluate_simulation(test_obs, sim_test),
        },
        calibration_config={
            "epochs": int(epochs),
            "pop_size": int(pop_size),
            "seed": seed,
            "objective": "minimize 1 - NSE on training set; unstable Muskingum parameter combinations are rejected",
            "parameter_bounds": {
                name: {"lower": DEFAULT_PARAMETER_BOUNDS[name][0], "upper": DEFAULT_PARAMETER_BOUNDS[name][1]}
                for name in PARAMETER_NAMES
            },
        },
        history=_extract_history(opt_model),
        series={
            "train": {
                "observed": [float(v) for v in train_obs[:n_train]],
                "simulated": [float(v) for v in sim_train[:n_train]],
            },
            "test": {
                "observed": [float(v) for v in test_obs[:n_test]],
                "simulated": [float(v) for v in sim_test[:n_test]],
            },
        },
    )


def calibrate_from_csv(
    data_csv: str | Path,
    area: float = 150.0,
    dt: float = 1.0,
    epochs: int = 100,
    pop_size: int = 80,
    train_ratio: float = 2.0 / 3.0,
    seed: int | None = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, CalibrationResult]:
    df = pd.read_csv(data_csv, encoding="utf-8-sig")
    train_df, test_df = split_calibration_data(df, train_ratio=train_ratio)
    result = calibrate_model(
        train_df=train_df,
        test_df=test_df,
        area=area,
        dt=dt,
        epochs=epochs,
        pop_size=pop_size,
        seed=seed,
    )
    return train_df, test_df, result


def _plot_hydro_and_rain(
    ax,
    time_values: np.ndarray,
    rainfall_mmh: np.ndarray,
    observed: np.ndarray,
    simulated: np.ndarray,
    title: str,
    metrics: dict[str, float | int | None],
    rain_color: str,
) -> None:
    n_cmp = min(len(time_values), len(observed), len(simulated))
    t = np.asarray(time_values[:n_cmp], dtype=float)
    observed = np.asarray(observed[:n_cmp], dtype=float)
    simulated = np.asarray(simulated[:n_cmp], dtype=float)
    rainfall = np.asarray(rainfall_mmh[: min(len(rainfall_mmh), n_cmp)], dtype=float)
    ax_rain = ax.twinx()
    if len(rainfall) > 0:
        bar_width = 0.85 * (np.median(np.diff(t)) if len(t) > 1 else 1.0)
        ax_rain.bar(t[: len(rainfall)], rainfall, width=bar_width, color=rain_color, alpha=0.45, edgecolor=rain_color, linewidth=0.2)
        rain_max = max(float(np.max(rainfall)), 1.0)
        ax_rain.set_ylim(rain_max * 3.2, 0.0)
    ax_rain.set_ylabel("Rainfall (mm/h)", fontsize=9, color=rain_color)
    ax_rain.tick_params(axis="y", labelcolor=rain_color, labelsize=8)

    ax.plot(t, observed, "o", color="0.35", markersize=3.5, alpha=0.7, label="Observed")
    ax.plot(t, simulated, color="firebrick", linewidth=2.0, label="Simulated")
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel("Time (h)", fontsize=9)
    ax.set_ylabel("Discharge (m3/s)", fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.85)
    if len(t) > 0:
        ax.set_xlim(float(np.min(t)) - 1.0, float(np.max(t)) + 1.0)
    text = (
        f"NSE = {metrics.get('NSE', float('nan')):.3f}\n"
        f"RMSE = {metrics.get('RMSE_m3s', float('nan')):.1f} m3/s\n"
        f"PBIAS = {metrics.get('PBIAS_pct', float('nan')):.1f}%"
    )
    ax.text(
        0.97,
        0.94,
        text,
        transform=ax.transAxes,
        fontsize=8,
        ha="right",
        va="top",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.85),
    )


def _plot_summary(result: CalibrationResult, train_df: pd.DataFrame, test_df: pd.DataFrame, path: Path) -> None:
    fig = plt.figure(figsize=(18, 11))
    gs = GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.28)

    ax1 = fig.add_subplot(gs[0, 0])
    _plot_hydro_and_rain(
        ax1,
        train_df["Time_h"].to_numpy(),
        train_df["Rainfall_mmh"].to_numpy(),
        np.asarray(result.series["train"]["observed"]),
        np.asarray(result.series["train"]["simulated"]),
        "Training Period (Calibration)",
        result.performance["train"],
        "steelblue",
    )

    ax2 = fig.add_subplot(gs[0, 1])
    _plot_hydro_and_rain(
        ax2,
        test_df["Time_h"].to_numpy(),
        test_df["Rainfall_mmh"].to_numpy(),
        np.asarray(result.series["test"]["observed"]),
        np.asarray(result.series["test"]["simulated"]),
        "Testing Period (Validation)",
        result.performance["test"],
        "darkorange",
    )

    ax3 = fig.add_subplot(gs[1, 0])
    train_obs = np.asarray(result.series["train"]["observed"])
    train_sim = np.asarray(result.series["train"]["simulated"])
    test_obs = np.asarray(result.series["test"]["observed"])
    test_sim = np.asarray(result.series["test"]["simulated"])
    ax3.scatter(train_obs, train_sim, c="steelblue", s=24, alpha=0.6, edgecolors="none", label="Train")
    ax3.scatter(test_obs, test_sim, c="darkorange", s=24, alpha=0.6, edgecolors="none", label="Test")
    max_value = max(float(np.max(train_obs)), float(np.max(train_sim)), float(np.max(test_obs)), float(np.max(test_sim)), 1.0)
    lims = [0.0, max_value * 1.08]
    ax3.plot(lims, lims, "k--", linewidth=1.0, alpha=0.55, label="1:1 line")
    ax3.set_xlim(lims)
    ax3.set_ylim(lims)
    ax3.set_xlabel("Observed Discharge (m3/s)", fontsize=9)
    ax3.set_ylabel("Simulated Discharge (m3/s)", fontsize=9)
    ax3.set_title("Observed vs Simulated", fontsize=11, fontweight="bold")
    ax3.grid(axis="both", alpha=0.25)
    ax3.legend(loc="upper left", fontsize=8)

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis("off")
    p = result.parameters
    lines = [
        ("Calibrated Parameters", True),
        ("", False),
        (f"Watershed area: {result.area_km2:.1f} km2    dt: {result.dt_h:.2f} h", False),
        ("", False),
        ("Green-Ampt", True),
        (f"  Ks            = {p['Ks']:.3e} m/s", False),
        (f"  suction_head  = {p['suction_head']:.4f} m", False),
        (f"  delta_theta   = {p['delta_theta']:.4f}", False),
        ("", False),
        ("Nash Unit Hydrograph", True),
        (f"  n             = {p['n']:.4f}", False),
        (f"  k             = {p['k']:.4f} h", False),
        ("", False),
        ("Muskingum Routing", True),
        (f"  K             = {p['K_musk']:.4f} h", False),
        (f"  x             = {p['x_musk']:.4f}", False),
        ("", False),
        ("Performance", True),
        (
            f"  Train NSE={result.performance['train']['NSE']:.4f}  "
            f"RMSE={result.performance['train']['RMSE_m3s']:.1f} m3/s",
            False,
        ),
        (
            f"  Test  NSE={result.performance['test']['NSE']:.4f}  "
            f"RMSE={result.performance['test']['RMSE_m3s']:.1f} m3/s",
            False,
        ),
    ]
    for i, (text, is_header) in enumerate(lines):
        ax4.text(
            0.05,
            0.97 - i * 0.045,
            text,
            transform=ax4.transAxes,
            fontsize=9.3,
            family="monospace",
            fontweight="bold" if is_header else "normal",
            color="#333333",
        )

    fig.suptitle("GreenAmpt-Nash-Muskingum Calibration and Validation", fontsize=15, fontweight="bold", y=0.985)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _plot_training_history(result: CalibrationResult, path: Path) -> None:
    fig, ax1 = plt.subplots(figsize=(11, 6))
    epoch = result.history.get("epoch", [])
    best_fitness = result.history.get("best_fitness", [])
    best_nse = result.history.get("best_nse", [])
    if epoch and best_fitness:
        ax1.plot(epoch, best_fitness, color="firebrick", linewidth=2.0, label="Best fitness (1 - NSE)")
        ax1.set_xlabel("WOA Epoch")
        ax1.set_ylabel("Best fitness", color="firebrick")
        ax1.tick_params(axis="y", labelcolor="firebrick")
        ax1.grid(axis="both", alpha=0.25)
        ax2 = ax1.twinx()
        ax2.plot(epoch, best_nse, color="steelblue", linewidth=2.0, label="Best NSE")
        ax2.set_ylabel("Best training NSE", color="steelblue")
        ax2.tick_params(axis="y", labelcolor="steelblue")
    else:
        ax1.text(0.5, 0.5, "Optimizer history unavailable", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_axis_off()
    fig.suptitle("Calibration Process", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _plot_fit_diagnostics(result: CalibrationResult, train_df: pd.DataFrame, test_df: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    periods = [
        ("Training Fit", "train", train_df, "steelblue"),
        ("Testing Fit", "test", test_df, "darkorange"),
    ]
    for col, (title, key, df, color) in enumerate(periods):
        observed = np.asarray(result.series[key]["observed"])
        simulated = np.asarray(result.series[key]["simulated"])
        n_cmp = min(len(observed), len(simulated), len(df))
        time_values = df["Time_h"].to_numpy()[:n_cmp]
        observed = observed[:n_cmp]
        simulated = simulated[:n_cmp]

        ax_ts = axes[0, col]
        ax_ts.plot(time_values, observed, "o-", color="0.35", markersize=3.5, linewidth=1.2, label="Observed")
        ax_ts.plot(time_values, simulated, color=color, linewidth=2.0, label="Simulated")
        ax_ts.set_title(title, fontsize=11, fontweight="bold")
        ax_ts.set_xlabel("Time (h)")
        ax_ts.set_ylabel("Discharge (m3/s)")
        ax_ts.grid(axis="y", alpha=0.25)
        ax_ts.legend(fontsize=8)

        ax_sc = axes[1, col]
        ax_sc.scatter(observed, simulated, c=color, s=30, alpha=0.65, edgecolors="none")
        max_value = max(float(np.max(observed)), float(np.max(simulated)), 1.0)
        lims = [0.0, max_value * 1.08]
        ax_sc.plot(lims, lims, "k--", linewidth=1.0, alpha=0.55)
        ax_sc.set_xlim(lims)
        ax_sc.set_ylim(lims)
        ax_sc.set_xlabel("Observed Discharge (m3/s)")
        ax_sc.set_ylabel("Simulated Discharge (m3/s)")
        metrics = result.performance[key]
        ax_sc.set_title(f"NSE={metrics['NSE']:.3f}, r={metrics.get('correlation')}", fontsize=10)
        ax_sc.grid(axis="both", alpha=0.25)

    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="steelblue", markersize=8, label="Training"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="darkorange", markersize=8, label="Testing"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.98), frameon=False)
    fig.suptitle("Train/Test Fit Diagnostics", fontsize=14, fontweight="bold", y=1.0)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_calibration_outputs(
    result: CalibrationResult,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_json: str | Path,
    figures_dir: str | Path,
    save_figures: bool = True,
) -> dict[str, Path]:
    output_json = Path(output_json)
    figures_dir = Path(figures_dir)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    payload = asdict(result)
    payload["calibration_history"] = payload.pop("history")
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    written: dict[str, Path] = {"params_json": output_json}
    if save_figures:
        summary_path = figures_dir / "train_result.png"
        training_path = figures_dir / "calibration_training_curve.png"
        fit_path = figures_dir / "train_test_fit.png"
        _plot_summary(result, train_df, test_df, summary_path)
        _plot_training_history(result, training_path)
        _plot_fit_diagnostics(result, train_df, test_df, fit_path)
        written.update(
            {
                "summary_figure": summary_path,
                "training_figure": training_path,
                "fit_figure": fit_path,
            }
        )
    return written


def run_calibration_workflow(
    data_csv: str | Path,
    output_json: str | Path,
    figures_dir: str | Path,
    area: float = 150.0,
    dt: float = 1.0,
    epochs: int = 100,
    pop_size: int = 80,
    train_ratio: float = 2.0 / 3.0,
    seed: int | None = 42,
    save_figures: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, CalibrationResult, dict[str, Path]]:
    train_df, test_df, result = calibrate_from_csv(
        data_csv=data_csv,
        area=area,
        dt=dt,
        epochs=epochs,
        pop_size=pop_size,
        train_ratio=train_ratio,
        seed=seed,
    )
    written = write_calibration_outputs(
        result=result,
        train_df=train_df,
        test_df=test_df,
        output_json=output_json,
        figures_dir=figures_dir,
        save_figures=save_figures,
    )
    return train_df, test_df, result, written
