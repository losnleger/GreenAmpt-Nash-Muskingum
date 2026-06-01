# -*- coding: UTF-8 -*-
"""
洪水预报脚本
============
加载率定好的参数 + 独立预报降雨 → 输出洪水预报结果 + 专业出图。

用法:
    python forecast.py
    python forecast.py my_rain.csv -p my_params.json
    python forecast.py my_rain.csv -o result.csv --plot result.png
"""

import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from core.model import GreenAmpt, MuskingumRouting, NashHydrographCalculator

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def load_params(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    p = data['parameters']
    params = [p['Ks'], p['suction_head'], p['delta_theta'],
              p['n'], p['k'], p['K_musk'], p['x_musk']]
    area = data['area_km2']
    dt = data['dt_h']
    perf = data.get('performance', {})
    print(f"加载参数: {json_path}")
    if 'train' in perf:
        print(f"  训练 NSE: {perf['train'].get('NSE', '?')},  "
              f"测试 NSE: {perf['test'].get('NSE', '?')}")
    else:
        print(f"  NSE: {perf.get('NSE', '?')}")
    print(f"  Ks={params[0]:.2e}  psi={params[1]:.3f}  "
          f"Dtheta={params[2]:.3f}  n={params[3]:.3f}  "
          f"k={params[4]:.3f}  K={params[5]:.3f}  x={params[6]:.3f}")
    return params, area, dt


def run_forecast(params, area, dt, fcst_csv_path,
                 output_csv=None, output_plot=None):
    Ks, suction, dtheta, n, k, K_musk, x_musk = params

    df = pd.read_csv(fcst_csv_path, encoding='utf-8-sig')

    # 支持两种列名: Forecast_Rainfall_mmh 或 Rainfall_mmh
    if 'Forecast_Rainfall_mmh' in df.columns:
        rain_col = 'Forecast_Rainfall_mmh'
    elif 'Rainfall_mmh' in df.columns:
        rain_col = 'Rainfall_mmh'
    else:
        raise ValueError("Forecast CSV must contain Forecast_Rainfall_mmh or Rainfall_mmh.")
    rain_mmh = df[rain_col].values
    rain_mps = rain_mmh / 1000 / 3600
    total_rain = float(rain_mmh.sum() * dt)

    print(f"\n加载预报降雨: {fcst_csv_path}")
    print(f"  历时: {len(rain_mmh)} h,  累计雨量: {total_rain:.1f} mm")
    print(f"  最大雨强: {rain_mmh.max():.1f} mm/h")

    print("运行预报...")
    ga = GreenAmpt(Ks, suction, dtheta, delta_t=dt * 3600)
    net_rain = np.array([ga.calculate_runoff(r) for r in rain_mps])
    nash = NashHydrographCalculator(n=n, k=k, area_km2=area, dt=dt)
    mk = MuskingumRouting(K=K_musk, x=x_musk, dt=dt)
    final_flow = mk.route_flow(nash.convolve_hydrograph(net_rain))

    peak_flow = float(np.max(final_flow))
    peak_time = int(np.argmax(final_flow))
    total_runoff = float(np.sum(net_rain))
    rc = total_runoff / total_rain * 100 if total_rain > 0 else 0.0
    print(f"  产流总量: {total_runoff:.1f} mm  (径流系数 {rc:.1f}%)")
    print(f"  预报洪峰: {peak_flow:.1f} m3/s  @ t = {peak_time} h")

    if output_csv:
        t_flow = np.arange(len(final_flow)) * dt
        df_out = pd.DataFrame({
            'Time_h': t_flow,
            'Discharge_m3s': np.round(final_flow, 2),
        })
        os.makedirs(os.path.dirname(output_csv) or '.', exist_ok=True)
        df_out.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"\n结果已保存: {output_csv}")

    if output_plot:
        fig, ax1 = plt.subplots(figsize=(14, 7))

        t_rain = np.arange(len(rain_mmh)) * dt

        # 降雨 — 倒置柱状图
        ax1r = ax1.twinx()
        ax1r.bar(t_rain, rain_mmh, width=dt * 0.85, color='darkorange',
                 alpha=0.45, edgecolor='darkorange', linewidth=0.2)
        ax1r.set_ylabel('Forecast Rainfall (mm/h)', fontsize=11,
                        color='darkorange')
        ax1r.tick_params(axis='y', labelcolor='darkorange', labelsize=9)
        ax1r.set_ylim(max(rain_mmh) * 3.2, 0)  # 倒置

        # 预报流量
        t_f = np.arange(len(final_flow)) * dt
        ax1.fill_between(t_f, 0, final_flow, alpha=0.25, color='firebrick')
        ax1.plot(t_f, final_flow, 'firebrick', linewidth=2.5)
        ax1.scatter(peak_time * dt, peak_flow, s=140, c='red', zorder=5,
                    marker='D', edgecolors='white', linewidths=1,
                    label=f'Peak: {peak_flow:.0f} m3/s @ t = {peak_time} h')
        ax1.set_xlabel('Time (h)', fontsize=11)
        ax1.set_ylabel('Discharge (m3/s)', fontsize=11)
        ax1.set_title('Flood Forecast', fontsize=14, fontweight='bold')
        ax1.set_xlim(-1, max(len(rain_mmh), len(final_flow)) * dt + 0.5)
        ax1.set_ylim(0, peak_flow * 1.18)
        ax1.legend(loc='upper left', fontsize=10, framealpha=0.8)
        ax1.grid(axis='y', alpha=0.25)

        # 文本标注
        info = (f"Total Rainfall: {total_rain:.0f} mm\n"
                f"Total Runoff:   {total_runoff:.0f} mm\n"
                f"Runoff Coef:    {rc:.1f}%")
        ax1.text(0.97, 0.85, info, transform=ax1.transAxes, fontsize=10,
                 ha='right', va='top', family='monospace',
                 bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.85))

        fig.suptitle('GreenAmpt-Nash-Muskingum Flood Forecast',
                     fontsize=15, fontweight='bold', y=0.98)
        fig.tight_layout()
        os.makedirs(os.path.dirname(output_plot) or '.', exist_ok=True)
        fig.savefig(output_plot, dpi=180, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        print(f"结果图已保存: {output_plot}")

    return {'peak_flow_m3s': peak_flow, 'peak_time_h': peak_time,
            'total_rainfall_mm': total_rain,
            'total_runoff_mm': total_runoff,
            'runoff_coefficient_pct': round(rc, 1),
            'flow_series': final_flow}


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description='运行洪水预报')
    p.add_argument('forecast_csv', nargs='?',
                   default=os.path.join('dataset', 'example_forecast.csv'),
                   help='预报降雨 CSV')
    p.add_argument('-p', '--params',
                   default=os.path.join('params', 'calibrated_params.json'),
                   help='率定参数 JSON')
    p.add_argument('-o', '--output',
                   default=os.path.join('outputs', 'forecast_result.csv'),
                   help='预报结果 CSV')
    p.add_argument('--plot',
                   default=os.path.join('outputs', 'forecast_result.png'),
                   help='结果图 PNG')
    args = p.parse_args()
    if not os.path.exists(args.forecast_csv):
        print(f"错误: 找不到 '{args.forecast_csv}'")
        return 1
    if not os.path.exists(args.params):
        print(f"错误: 找不到参数文件 '{args.params}'")
        print("请先运行: python calibrate.py")
        return 1
    params, area, dt = load_params(args.params)
    run_forecast(params, area, dt, args.forecast_csv,
                 output_csv=args.output, output_plot=args.plot)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
