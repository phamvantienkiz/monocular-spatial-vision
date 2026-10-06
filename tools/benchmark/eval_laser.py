"""Benchmark Evaluation and Report Generator.

Reads laser benchmark trials and generates a Markdown report with
AbsRel, RMSE, and Pass/Fail verification against AC-02 (AbsRel <= 5.0%).

Usage:
    python tools/benchmark/eval_laser.py --data data/benchmark_trials.json --output reports/benchmark_report.md
"""

import argparse
import json
import math
import os


def generate_report(data_file: str, output_report: str):
    if not os.path.isfile(data_file):
        print(f"[!] Benchmark data file {data_file} not found.")
        return

    with open(data_file, "r") as f:
        trials = json.load(f)

    if not trials:
        print("[!] No trials found in data file.")
        return

    total = len(trials)
    passed_count = 0
    sq_errors = []
    abs_rels = []

    rows = []
    for t in trials:
        t_id = t["target_id"]
        t_name = t.get("target_name", f"Target_{t_id}")
        d_gt = t["laser_distance_m"]
        d_pred = t["estimated_distance_m"]

        abs_err = abs(d_pred - d_gt)
        abs_rel = (abs_err / d_gt) * 100.0 if d_gt > 0 else 0.0
        passed = abs_rel <= 5.0

        if passed:
            passed_count += 1
        sq_errors.append(abs_err ** 2)
        abs_rels.append(abs_rel)

        status_badge = "✅ PASS" if passed else "❌ FAIL"
        rows.append(f"| {t_id} | {t_name} | {d_gt:.3f} | {d_pred:.3f} | {abs_err:.3f} | {abs_rel:.2f}% | {status_badge} |")

    rmse = math.sqrt(sum(sq_errors) / total)
    mean_abs_rel = sum(abs_rels) / total
    pass_rate = (passed_count / total) * 100.0

    report_content = f"""# Laser Ground Truth Benchmark Report — Release 1

> **Generated Date:** 2026-10-06  
> **Evaluation Rig:** Bosch GLM Laser Meter (±1.5mm)  
> **Criteria:** AC-02 AbsRel <= 5.0% on range 0.5m - 3.0m  

---

## 1. Summary Metrics
- **Total Samples:** {total}
- **Pass Rate:** {pass_rate:.1f}% ({passed_count}/{total})
- **Mean AbsRel:** {mean_abs_rel:.2f}%
- **Root Mean Squared Error (RMSE):** {rmse:.4f} m

---

## 2. Detailed Trial Observations
| ID | Target Name | Laser GT (m) | Estimated (m) | Abs Error (m) | AbsRel (%) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
""" + "\n".join(rows) + "\n"

    os.makedirs(os.path.dirname(output_report), exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"[+] Saved benchmark report to {output_report}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Laser Benchmark Trials")
    parser.add_argument("--data", default="data/benchmark_trials.json", help="Path to trial JSON data")
    parser.add_argument("--output", default="docs/reports/benchmark_release1_results.md", help="Output report path")
    args = parser.parse_args()
    generate_report(args.data, args.output)
