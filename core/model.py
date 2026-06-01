# -*- coding: UTF-8 -*-
"""Core Green-Ampt, Nash unit hydrograph, and Muskingum routing model."""

from __future__ import annotations

import numpy as np
from scipy.special import gamma


def get_prob_column(probability, columns, prefix="p="):
    """Find the rainfall column closest to a requested exceedance probability."""
    best_match = None
    smallest_diff = float("inf")
    for col in columns:
        col_str = str(col).strip().lower()
        if prefix in col_str and "%" in col_str:
            try:
                val_str = col_str.split(prefix)[-1].replace("%", "").replace(")", "")
                val = float(val_str)
                diff = abs(val - probability)
                if diff < smallest_diff:
                    smallest_diff = diff
                    best_match = col
            except ValueError:
                continue
    if best_match is None:
        raise KeyError(f"No suitable column found for probability {probability}")
    return best_match


class GreenAmpt:
    """Green-Ampt infiltration model.

    Inputs use SI units internally: rainfall intensity in m/s and time step in
    seconds. The returned excess rainfall depth is in mm for the current step.
    """

    def __init__(self, Ks, suction_head, delta_theta, delta_t=3600):
        if Ks <= 0:
            raise ValueError("Ks must be positive.")
        if suction_head <= 0:
            raise ValueError("suction_head must be positive.")
        if delta_theta <= 0:
            raise ValueError("delta_theta must be positive.")
        if delta_t <= 0:
            raise ValueError("delta_t must be positive.")

        self.Ks = float(Ks)
        self.suction_head = float(suction_head)
        self.delta_theta = float(delta_theta)
        self.delta_t = float(delta_t)
        self.F = 0.0

    def calculate_runoff(self, rainfall_intensity):
        """Calculate excess rainfall depth for one step, in mm."""
        rainfall_intensity = float(rainfall_intensity)
        if rainfall_intensity < 0:
            raise ValueError("rainfall_intensity must be non-negative.")

        if self.F < 1e-9:
            infiltration_capacity = float("inf")
        else:
            infiltration_capacity = self.Ks * (1 + (self.suction_head * self.delta_theta) / self.F)

        total_rain = rainfall_intensity * self.delta_t
        actual_infiltration = min(total_rain, infiltration_capacity * self.delta_t)
        runoff = total_rain - actual_infiltration
        self.F += actual_infiltration
        return max(round(runoff * 1000, 2), 0.0)


class NashHydrographCalculator:
    """Nash instantaneous unit hydrograph calculator."""

    def __init__(self, n, k, area_km2, dt):
        if n <= 0:
            raise ValueError("n must be positive.")
        if k <= 0:
            raise ValueError("k must be positive.")
        if area_km2 <= 0:
            raise ValueError("area_km2 must be positive.")
        if dt <= 0:
            raise ValueError("dt must be positive.")

        self.n = float(n)
        self.k = float(k)
        self.area = float(area_km2)
        self.dt = float(dt)
        self.unit_hydrograph = None
        self.flood_flow = None

    def compute_unit_hydrograph(self, duration=24):
        """Compute and normalize a discrete Nash unit hydrograph."""
        if duration <= 0:
            raise ValueError("duration must be positive.")
        k = max(self.k, 1e-3)
        t = np.arange(0, duration, self.dt)
        with np.errstate(divide="ignore", invalid="ignore"):
            U = (1 / (k * gamma(self.n))) * (t / k) ** (self.n - 1) * np.exp(-t / k)
            U[np.isnan(U)] = 0
            U[np.isinf(U)] = 0
        self.unit_hydrograph = U / np.sum(U) if np.sum(U) > 0 else np.zeros_like(U)
        return self.unit_hydrograph

    def _unit_conversion(self, runoff_mm):
        """Convert runoff depth in mm per step to discharge in m3/s."""
        return (runoff_mm * self.area * 1e6 / 1000) / (self.dt * 3600)

    def convolve_hydrograph(self, net_rain):
        """Convolve excess rainfall depth with the unit hydrograph."""
        net_rain = np.asarray(net_rain, dtype=float)
        if len(net_rain) == 0:
            raise ValueError("net_rain must not be empty.")
        if np.any(net_rain < 0):
            raise ValueError("net_rain must be non-negative.")
        if self.unit_hydrograph is None:
            self.compute_unit_hydrograph(duration=len(net_rain) * 2)
        full_conv = np.convolve(net_rain, self.unit_hydrograph, mode="full")
        self.flood_flow = self._unit_conversion(full_conv)
        return self.flood_flow

    @property
    def peak_flow(self):
        return np.max(self.flood_flow) if self.flood_flow is not None else None


def muskingum_stability_bounds(K, dt):
    """Return the stable x interval for a Muskingum step.

    The explicit Muskingum coefficients are non-negative when
    2*K*x <= dt <= 2*K*(1-x), with 0 <= x <= 0.5.
    """
    if K <= 0:
        raise ValueError("K must be positive.")
    if dt <= 0:
        raise ValueError("dt must be positive.")
    upper = min(0.5, dt / (2.0 * K), 1.0 - dt / (2.0 * K))
    lower = 0.0
    return lower, upper


def is_muskingum_stable(K, x, dt):
    """Return True when Muskingum K, x, and dt satisfy coefficient stability."""
    if K <= 0 or dt <= 0 or x < 0 or x > 0.5:
        return False
    _, upper = muskingum_stability_bounds(K, dt)
    if upper < 0:
        return False
    return x <= upper + 1e-12


class MuskingumRouting:
    """Muskingum channel routing model.

    This class rejects unstable parameter combinations instead of silently
    editing K or x. Calibration code should penalize invalid combinations.
    """

    def __init__(self, K, x, dt):
        if K <= 0:
            raise ValueError("K must be positive.")
        if dt <= 0:
            raise ValueError("dt must be positive.")
        if x < 0 or x > 0.5:
            raise ValueError("x must be between 0 and 0.5.")
        if not is_muskingum_stable(K, x, dt):
            lower, upper = muskingum_stability_bounds(K, dt)
            raise ValueError(
                "Unstable Muskingum parameters: require 2*K*x <= dt <= 2*K*(1-x); "
                f"for K={K:g}, dt={dt:g}, stable x is [{lower:g}, {upper:g}]."
            )

        self.K = float(K)
        self.x = float(x)
        self.dt = float(dt)
        self.C0, self.C1, self.C2 = self._calculate_coefficients()

    def _calculate_coefficients(self):
        denominator = 2 * self.K * (1 - self.x) + self.dt
        C0 = (-2 * self.K * self.x + self.dt) / denominator
        C1 = (2 * self.K * self.x + self.dt) / denominator
        C2 = (2 * self.K * (1 - self.x) - self.dt) / denominator
        return C0, C1, C2

    def route_flow(self, inflow):
        """Route inflow hydrograph through the Muskingum reach."""
        inflow = np.asarray(inflow, dtype=float)
        if len(inflow) == 0:
            raise ValueError("inflow must not be empty.")
        if np.any(inflow < 0):
            raise ValueError("inflow must be non-negative.")

        outflow = np.zeros_like(inflow)
        outflow[0] = inflow[0]
        for i in range(1, len(inflow)):
            I2 = inflow[i]
            I1 = inflow[i - 1]
            O1 = outflow[i - 1]
            outflow[i] = self.C0 * I2 + self.C1 * I1 + self.C2 * O1
            outflow[i] = max(outflow[i], 0.0)
        return outflow


def simulate_with_best_params(best_params, rain_seq, area_km2, dt):
    """Run the full model for a rainfall intensity sequence in m/s."""
    Ks, suction_head, delta_theta, n, k, K_musk, x_musk = best_params
    ga = GreenAmpt(Ks, suction_head, delta_theta, delta_t=dt * 3600.0)
    net_rain_mm = np.array([ga.calculate_runoff(r) for r in rain_seq])
    nash = NashHydrographCalculator(n=n, k=k, area_km2=area_km2, dt=dt)
    nash_flow = nash.convolve_hydrograph(net_rain_mm)
    muskingum = MuskingumRouting(K=K_musk, x=x_musk, dt=dt)
    final_flow = muskingum.route_flow(nash_flow)
    return net_rain_mm, nash_flow, final_flow
