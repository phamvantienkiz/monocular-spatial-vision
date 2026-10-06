"""Benchmark Evaluation Service.

Calculates quantitative error metrics against Bosch GLM Laser Ground Truth:
- Absolute Error = |Z_pred - Z_gt|
- Absolute Relative Error (AbsRel) = (|Z_pred - Z_gt| / Z_gt) * 100%
- Root Mean Squared Error (RMSE) across test sessions

TODO for Students:
- Store benchmark trials in memory or SQLite database.
- Evaluate Pass/Fail status against the <= 5.0% AbsRel criterion.
- Export summary results to markdown or CSV format.
"""

from typing import List
from app.schemas.benchmark import LaserBenchmarkEntry, BenchmarkResult


class BenchmarkService:
    """Manages ground-truth laser comparisons and QA acceptance criteria."""

    def __init__(self):
        self._history: List[BenchmarkResult] = []

    def evaluate_entry(self, entry: LaserBenchmarkEntry) -> BenchmarkResult:
        """Evaluates a single measurement against ground truth."""
        abs_err = abs(entry.estimated_distance_m - entry.laser_distance_m)
        abs_rel = (abs_err / entry.laser_distance_m) * 100.0 if entry.laser_distance_m > 0 else 0.0
        passed = abs_rel <= 5.0

        res = BenchmarkResult(
            target_id=entry.target_id,
            laser_distance_m=entry.laser_distance_m,
            estimated_distance_m=entry.estimated_distance_m,
            abs_error_m=round(abs_err, 4),
            abs_rel_pct=round(abs_rel, 2),
            is_passed=passed,
        )
        self._history.append(res)
        return res

    def get_summary(self) -> dict:
        """Computes summary metrics (mean AbsRel, total pass rate)."""
        if not self._history:
            return {"total_samples": 0, "pass_rate_pct": 0.0, "mean_abs_rel_pct": 0.0}

        total = len(self._history)
        passed = sum(1 for r in self._history if r.is_passed)
        mean_abs_rel = sum(r.abs_rel_pct for r in self._history) / total

        return {
            "total_samples": total,
            "pass_rate_pct": round((passed / total) * 100.0, 1),
            "mean_abs_rel_pct": round(mean_abs_rel, 2),
        }
