#!/usr/bin/env python3
"""
Drone Simulation Analysis Script

Analyzes output from harsh_simulation.py and generates summary report.
Supports both real-time log parsing and post-hoc JSON telemetry analysis.

Usage:
    python3 analyze_simulation.py --log simulation.log
    python3 analyze_simulation.py --json telemetry.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class SimSample:
    """Single simulation sample."""

    time_s: float
    failsafe: str
    battery_pct: float
    missions: int
    alt_m: float
    roll_deg: float


@dataclass
class SimAnalysis:
    """Complete simulation analysis results."""

    duration_s: float
    total_samples: int

    # Failsafe
    failsafe_normal_pct: float
    failsafe_rtl_pct: float
    failsafe_other_pct: float

    # Battery
    battery_start: float
    battery_end: float
    battery_drain_rate: float  # %/hour

    # Altitude
    alt_mean: float
    alt_std: float
    alt_min: float
    alt_max: float

    # Roll (attitude stability)
    roll_mean: float
    roll_std: float
    roll_min: float
    roll_max: float

    # Mission
    missions_completed: int

    # Status
    stability_score: float  # 0-10


def parse_log_line(line: str) -> Optional[SimSample]:
    """Parse a REPORT line from simulation output."""
    # [REPORT] T=35.1s | FS=NORMAL | Bat=99.6% | Mis=0 | Alt=54.2m | Roll=-5.6
    pattern = r"\[REPORT\] T=(\d+\.?\d*)s \| FS=(\w+) \| Bat=(\d+\.?\d*)% \| Mis=(\d+) \| Alt=(-?\d+\.?\d*)m \| Roll=(-?\d+\.?\d*)"
    match = re.search(pattern, line)
    if not match:
        return None
    return SimSample(
        time_s=float(match.group(1)),
        failsafe=match.group(2),
        battery_pct=float(match.group(3)),
        missions=int(match.group(4)),
        alt_m=float(match.group(5)),
        roll_deg=float(match.group(6)),
    )


def analyze_samples(samples: List[SimSample]) -> SimAnalysis:
    """Compute analysis from samples."""
    if not samples:
        raise ValueError("No samples to analyze")

    n = len(samples)
    duration = samples[-1].time_s - samples[0].time_s

    # Failsafe counts
    fs_counts = defaultdict(int)
    for s in samples:
        fs_counts[s.failsafe.upper()] += 1

    # Battery
    bat_start = samples[0].battery_pct
    bat_end = samples[-1].battery_pct
    drain_rate = (bat_start - bat_end) / (duration / 3600) if duration > 0 else 0

    # Altitude stats
    alts = [s.alt_m for s in samples]
    alt_mean = sum(alts) / n
    alt_std = (sum((a - alt_mean) ** 2 for a in alts) / n) ** 0.5

    # Roll stats
    rolls = [s.roll_deg for s in samples]
    roll_mean = sum(rolls) / n
    roll_std = (sum((r - roll_mean) ** 2 for r in rolls) / n) ** 0.5

    # Missions
    missions = max(s.missions for s in samples)

    # Stability score (0-10)
    # Penalize: high roll std, high alt std, low normal%, high drain
    score = 10.0
    if roll_std > 15:
        score -= 2.0
    elif roll_std > 10:
        score -= 1.0
    if alt_std > 15:
        score -= 2.0
    elif alt_std > 10:
        score -= 1.0
    if fs_counts.get("NORMAL", 0) / n < 0.9:
        score -= 2.0
    if drain_rate > 10:
        score -= 1.0
    score = max(0.0, min(10.0, score))

    return SimAnalysis(
        duration_s=duration,
        total_samples=n,
        failsafe_normal_pct=100 * fs_counts.get("NORMAL", 0) / n,
        failsafe_rtl_pct=100 * fs_counts.get("RTL", 0) / n,
        failsafe_other_pct=100
        * (n - fs_counts.get("NORMAL", 0) - fs_counts.get("RTL", 0))
        / n,
        battery_start=bat_start,
        battery_end=bat_end,
        battery_drain_rate=drain_rate,
        alt_mean=alt_mean,
        alt_std=alt_std,
        alt_min=min(alts),
        alt_max=max(alts),
        roll_mean=roll_mean,
        roll_std=roll_std,
        roll_min=min(rolls),
        roll_max=max(rolls),
        missions_completed=missions,
        stability_score=score,
    )


def generate_report(analysis: SimAnalysis) -> str:
    """Generate markdown report from analysis."""
    lines = [
        "# 🚁 Drone Simulation Analysis Report",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Duration | {analysis.duration_s:.1f}s ({analysis.duration_s / 3600:.2f}h) |",
        f"| Total Samples | {analysis.total_samples} |",
        f"| Stability Score | **{analysis.stability_score:.1f}/10** |",
        "",
        "## Failsafe Status",
        "",
        f"| State | Percentage |",
        f"|-------|------------|",
        f"| NORMAL | {analysis.failsafe_normal_pct:.1f}% |",
        f"| RTL | {analysis.failsafe_rtl_pct:.1f}% |",
        f"| Other | {analysis.failsafe_other_pct:.1f}% |",
        "",
        "## Battery",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Start | {analysis.battery_start:.1f}% |",
        f"| End | {analysis.battery_end:.1f}% |",
        f"| Drain Rate | {analysis.battery_drain_rate:.2f}%/hour |",
        "",
        "## Altitude Stability",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Mean | {analysis.alt_mean:.1f}m |",
        f"| Std Dev | {analysis.alt_std:.1f}m |",
        f"| Range | {analysis.alt_min:.1f}m ~ {analysis.alt_max:.1f}m |",
        "",
        "## Attitude Stability (Roll)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Mean | {analysis.roll_mean:.1f}° |",
        f"| Std Dev | {analysis.roll_std:.1f}° |",
        f"| Range | {analysis.roll_min:.1f}° ~ {analysis.roll_max:.1f}° |",
        "",
        "## Mission",
        "",
        f"- Missions Completed: {analysis.missions_completed}",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze drone simulation results")
    parser.add_argument("--log", type=Path, help="Path to simulation log file")
    parser.add_argument("--json", type=Path, help="Path to JSON telemetry file")
    parser.add_argument("--out", type=Path, help="Output markdown report path")
    args = parser.parse_args()

    samples: List[SimSample] = []

    if args.log:
        with open(args.log) as f:
            for line in f:
                sample = parse_log_line(line)
                if sample:
                    samples.append(sample)
    elif args.json:
        with open(args.json) as f:
            data = json.load(f)
        for entry in data.get("samples", []):
            samples.append(SimSample(**entry))
    else:
        # Read from stdin
        for line in sys.stdin:
            sample = parse_log_line(line)
            if sample:
                samples.append(sample)

    if not samples:
        print("No samples found!", file=sys.stderr)
        sys.exit(1)

    analysis = analyze_samples(samples)
    report = generate_report(analysis)

    if args.out:
        args.out.write_text(report)
        print(f"Report written to: {args.out}")
        # Also save JSON
        json_path = args.out.with_suffix(".json")
        json_path.write_text(json.dumps(asdict(analysis), indent=2))
        print(f"JSON written to: {json_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
