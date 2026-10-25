#!/usr/bin/env python3
"""Measure the CT meter's offset against your billing meter's hourly data.

Usage:
    python3 calibrate.py history.csv billing.csv [options]

history.csv  Home Assistant History export (columns: entity_id, state, last_changed) covering
             the grid channel's raw energy counters, plus about an hour either side of the
             billing period.
billing.csv  Interval billing data with the columns: start, import_kwh, export_kwh, and
             optionally end (start/end in ISO format with a time zone, for example
             2026-10-10T00:00:00+11:00). Without an end column, each row is one hour.
             Hourly data is recommended; 30-minute data also works.

Only the Python standard library is used. See CALIBRATION.md for the full method.
"""
import argparse
import bisect
import csv
import statistics
import sys
from datetime import datetime, timedelta


def parse_time(text):
    text = text.strip().replace("Z", "+00:00")
    t = datetime.fromisoformat(text)
    if t.tzinfo is None:
        sys.exit(f"Time without a time zone: {text!r}. Add one, for example +10:00.")
    return t


def load_history(path, entities):
    series = {e: [] for e in entities}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            e = row.get("entity_id")
            if e in series:
                try:
                    v = float(row["state"])
                except ValueError:
                    continue  # unknown / unavailable
                series[e].append((parse_time(row["last_changed"]).timestamp(), v))
    for e, pts in series.items():
        if not pts:
            sys.exit(f"No numeric readings for {e} in {path}.")
        pts.sort()
    return series


def interp(points, ts):
    """Counter value at time ts, interpolated linearly between the readings either side."""
    times = [p[0] for p in points]
    i = bisect.bisect_left(times, ts)
    if i == 0 or i == len(points):
        return None  # outside the exported range
    (t0, v0), (t1, v1) = points[i - 1], points[i]
    return v0 + (v1 - v0) * (ts - t0) / (t1 - t0) if t1 > t0 else v1


def max_gap_minutes(points, start, end):
    times = [p[0] for p in points if start <= p[0] <= end]
    edges = [start] + times + [end]
    return max(b - a for a, b in zip(edges, edges[1:])) / 60


def fit(xs, ys):
    """Least-squares line y = a + b x."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return my - mx, 1.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("history")
    ap.add_argument("billing")
    ap.add_argument("--import-entity", default="sensor.5_channel_energy_meter_channel_1_energy_consumed")
    ap.add_argument("--export-entity", default="sensor.5_channel_energy_meter_channel_1_energy_produced")
    ap.add_argument("--power-entity", default="sensor.5_channel_energy_meter_channel_1_power",
                    help="used to skip hours with gaps in readings (optional; leave it out of the export to skip the check)")
    ap.add_argument("--max-gap", type=float, default=10, help="skip hours with a reading gap longer than this (minutes)")
    ap.add_argument("--hours", action="store_true", help="print every hour")
    a = ap.parse_args()

    wanted = [a.import_entity, a.export_entity]
    with open(a.history, newline="", encoding="utf-8-sig") as f:
        present = {row.get("entity_id") for row in csv.DictReader(f)}
    use_power = a.power_entity in present
    if use_power:
        wanted.append(a.power_entity)
    s = load_history(a.history, wanted)

    rows = []
    with open(a.billing, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            start = parse_time(r["start"])
            end = parse_time(r["end"]) if r.get("end") else start + timedelta(hours=1)
            rows.append((start, end, float(r["import_kwh"]), float(r["export_kwh"])))
    rows.sort()

    hours, skipped = [], 0
    for start, end, b_imp, b_exp in rows:
        t0, t1 = start.timestamp(), end.timestamp()
        span_h = (t1 - t0) / 3600
        vals = [interp(s[e], t) for e in (a.import_entity, a.export_entity) for t in (t0, t1)]
        if None in vals:
            skipped += 1
            continue
        if use_power and max_gap_minutes(s[a.power_entity], t0, t1) > a.max_gap:
            skipped += 1
            continue
        c_imp, c_exp = vals[1] - vals[0], vals[3] - vals[2]
        gap_w = ((b_imp - b_exp) - (c_imp - c_exp)) * 1000 / span_h
        hours.append((start, b_imp / span_h, b_exp / span_h, c_imp / span_h, c_exp / span_h, gap_w))

    if len(hours) < 24:
        print(f"Only {len(hours)} usable intervals; at least three days' worth is recommended.")
        if not hours:
            sys.exit(1)

    if a.hours:
        print("interval start             bill imp  bill exp  CT imp   CT exp   net gap W   (kWh per hour)")
        for h in hours:
            print(f"{h[0].isoformat():26} {h[1]:8.3f}  {h[2]:8.3f}  {h[3]:7.3f}  {h[4]:7.3f}  {h[5]:9.1f}")
        print()

    gaps = [h[5] for h in hours]
    imp_only = [h for h in hours if h[2] == 0 and h[4] < 0.005]
    exp_only = [h for h in hours if h[1] <= 0.03 and h[2] > 0.2]
    print(f"Usable intervals: {len(hours)} (skipped {skipped}: outside the history or with reading gaps)")
    print(f"Net gap, all hours:    median {statistics.median(gaps):6.1f} W   mean {statistics.mean(gaps):6.1f} W")
    if len(imp_only) >= 5:
        ai, bi = fit([h[3] for h in imp_only], [h[1] for h in imp_only])
        print(f"Import-only hours ({len(imp_only)}): median gap {statistics.median(h[1] * 1000 - h[3] * 1000 for h in imp_only):6.1f} W;"
              f" fit: bill = {ai * 1000:.1f} W + {bi:.4f} x CT")
        if abs(bi - 1) > 0.01:
            print("  Note: the slope differs from 1 by more than 1 %: there may be a scaling error as well as an"
                  " offset. An offset correction alone won't remove it (see CALIBRATION.md).")
    if len(exp_only) >= 3:
        print(f"Export-only hours ({len(exp_only)}): median {statistics.median(h[4] * 1000 - h[2] * 1000 for h in exp_only):6.1f} W"
              " (CT export minus bill export)")
    days = {}
    for h in hours:
        days.setdefault(h[0].date(), []).append(h[5])
    full = {d: g for d, g in days.items() if len(g) >= 20}
    if len(full) >= 2:
        print()
        print("Per day (days with at least 20 usable hours):")
        for d, g in sorted(full.items()):
            print(f"  {d}  mean gap {statistics.mean(g):6.1f} W  ({len(g)} h)")
        means = [statistics.mean(g) for g in full.values()]
        print(f"  Day-to-day spread: {min(means):.1f} to {max(means):.1f} W"
              f" (standard deviation {statistics.pstdev(means):.1f} W)")
        if len(full) < 14:
            print("  The offset can vary from day to day; two weeks or more gives a steadier figure.")
    print()
    print(f"Suggested offset: {statistics.mean(gaps):.0f} W"
          " (add to net grid power; positive means the CT reads too little import / too much export)")
    print("  This is the mean over all usable hours, which is what makes energy totals match.")
    print(f"  The median ({statistics.median(gaps):.0f} W) shows a typical hour; a big difference between the two")
    print("  means a few hours (often rapid import/export switching) disagree strongly.")


if __name__ == "__main__":
    main()
