# -*- coding: UTF-8 -*-
"""Backward-compatible one-command training demo.

The real calibration implementation lives in ``calibrate.py`` and
``core.calibration_workflow``. Keep this file as a thin entry point so older
usage of ``python train.py`` still works without duplicating the workflow.
"""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from calibrate import calibrate


def main() -> int:
    calibrate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
