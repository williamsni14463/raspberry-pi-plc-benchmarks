#!/usr/bin/env python3
"""
analyze_latency.py

Reduces a latency CSV from modbus_latency_characterization.py into the summary
statistics quoted in the README, and optionally plots the histogram and CDF.

The point of reporting percentiles rather than mean and standard deviation is
that latency distributions are not Gaussian. They have a hard floor (you cannot
beat the cost of two TCP transactions) and a long right tail (scheduler
preemption). Mean and sigma describe neither feature well, which is why the
3-sigma bound in the raw data flags 0.185% of samples while the real question
is how far the worst sample actually got.

Usage:
    python3 analyze_latency.py data/modbus_latency_1.0ms_20260716_230441.csv
    python3 analyze_latency.py data/*.csv --plot

Stdlib only unless --plot is given.
"""

import argparse
import csv
import math
import statistics
import sys
from pathlib import Path


def load(path):
    """Pull latency_ms out of a results CSV, skipping any summary preamble.

    The characterization script writes a couple of human-readable lines above
    the header, so we cannot hand the file straight to DictReader.
    """
    rows, cycle = [], None
    with open(path, newline="") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 2 or not parts[0].isdigit():
                continue
            try:
                rows.append(float(parts[1]))
                if cycle is None and len(parts) >= 3:
                    cycle = float(parts[2])
            except ValueError:
                continue
    return rows, cycle


def percentile(sorted_vals, q):
    """Nearest-rank percentile. Fine for n in the thousands."""
    if not sorted_vals:
        return float("nan")
    i = int(round(q / 100.0 * (len(sorted_vals) - 1)))
    return sorted_vals[min(max(i, 0), len(sorted_vals) - 1)]


def summarize(latencies, cycle_ms):
    s = sorted(latencies)
    n = len(s)
    floor = percentile(s, 10)
    mean = sum(s) / n
    over = [x for x in s if cycle_ms and x > cycle_ms]

    return {
        "n": n,
        "cycle_ms": cycle_ms,
        "min": s[0],
        "floor_p10": floor,
        "median": percentile(s, 50),
        "mean": mean,
        "stdev": statistics.pstdev(s),
        "p90": percentile(s, 90),
        "p99": percentile(s, 99),
        "p999": percentile(s, 99.9),
        "max": s[-1],
        "overruns": len(over),
        "overrun_pct": 100.0 * len(over) / n if n else float("nan"),
        # Quantization check: if the trigger lands uniformly inside the scan
        # window, the mean should sit half a cycle above the floor.
        "mean_minus_floor": mean - floor,
        "expected_mean_minus_floor": cycle_ms / 2 if cycle_ms else float("nan"),
    }


def report(path, r):
    print(f"\n{path}")
    print(f"  n = {r['n']}, scan cycle = {r['cycle_ms']} ms")
    for label, key in [
        ("min", "min"), ("floor (p10)", "floor_p10"), ("median", "median"),
        ("mean", "mean"), ("std dev", "stdev"), ("p90", "p90"),
        ("p99", "p99"), ("p99.9", "p999"), ("max", "max"),
    ]:
        print(f"    {label:14s} {r[key]:8.4f} ms")
    print(f"    overruns       {r['overruns']:8d}  ({r['overrun_pct']:.2f}% of samples)")
    print(f"    mean - floor   {r['mean_minus_floor']:8.4f} ms "
          f"(expect ~{r['expected_mean_minus_floor']:.3f} if uniform in the window)")

    # Sanity checks that have caught real problems before.
    if r["floor_p10"] > r["cycle_ms"]:
        print("    !! floor exceeds the scan cycle — the measurement is "
              "communication-bound, not scan-bound")
    if r["max"] > 10 * r["cycle_ms"]:
        print("    !! worst case is more than 10 cycles — check for a sensor or "
              "SPI read inside the timed loop")


def plot(datasets, outdir):
    import matplotlib.pyplot as plt  # imported late so the CLI works without it

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for name, vals, cycle in datasets:
        ax1.hist(vals, bins=120, alpha=0.6, label=f"{name} ({cycle} ms cycle)")
        s = sorted(vals)
        ax2.plot(s, [i / len(s) for i in range(len(s))], label=name)
    for ax, title, xl in [(ax1, "Latency distribution", "latency [ms]"),
                          (ax2, "Cumulative distribution", "latency [ms]")]:
        ax.set_title(title)
        ax.set_xlabel(xl)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    ax1.set_ylabel("count")
    ax2.set_ylabel("fraction of samples")
    fig.tight_layout()
    out = Path(outdir) / "latency_summary.png"
    fig.savefig(out, dpi=150)
    print(f"\nwrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", help="results CSV file(s)")
    ap.add_argument("--plot", action="store_true", help="also write a figure")
    ap.add_argument("--outdir", default=".", help="where to put the figure")
    args = ap.parse_args()

    datasets = []
    for path in args.csv:
        vals, cycle = load(path)
        if not vals:
            print(f"{path}: no latency rows found", file=sys.stderr)
            continue
        report(path, summarize(vals, cycle))
        datasets.append((Path(path).stem, vals, cycle))

    if args.plot and datasets:
        plot(datasets, args.outdir)


if __name__ == "__main__":
    main()
