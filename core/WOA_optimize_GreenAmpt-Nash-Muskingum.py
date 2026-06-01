# -*- coding: UTF-8 -*-
"""Compatibility shim for the historical model module name.

The public, importable implementation now lives in ``core.model``. This file is
kept so older dynamic imports that target the historical filename can still find
the core model classes. The previous private Excel demo entrypoint was removed
for open-source release hygiene.
"""

from core.model import (  # noqa: F401
    GreenAmpt,
    MuskingumRouting,
    NashHydrographCalculator,
    get_prob_column,
    is_muskingum_stable,
    muskingum_stability_bounds,
    simulate_with_best_params,
)


def main() -> int:
    print("This compatibility module only re-exports core.model.")
    print("Use: python generate_example_data.py")
    print("Then: python calibrate.py dataset/example_data.csv")
    print("Then: python forecast.py dataset/example_forecast.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
