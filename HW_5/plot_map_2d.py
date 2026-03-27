"""
Plot sparse map from world_map_points.py CSV (top-down X–Y).

Usage:
  Same interpreter as for AirSim (venv): .\\AirSim\\PythonClient\\detection\\venv310\\Scripts\\python.exe -m pip install matplotlib
  .\\AirSim\\PythonClient\\detection\\venv310\\Scripts\\python.exe ALL_HW\\HW_5\\plot_map_2d.py ALL_HW\\HW_5\\map_points.csv -o ALL_HW\\HW_5\\map_topdown.png
"""

from __future__ import print_function

import argparse
import csv
import os
import sys

import numpy as np

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba
except ImportError:
    py = sys.executable or "python"
    print(
        "matplotlib is not installed for this Python. Run:\n  %s -m pip install matplotlib"
        % py,
        file=sys.stderr,
    )
    sys.exit(1)


def object_kind(mesh_name):
    """First '_' segment, e.g. Bench_01_53 → Bench, Small_House_31 → Small (readable legend)."""
    n = (mesh_name or "").strip()
    if not n:
        return "?"
    return n.split("_", 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", help="CSV from world_map_points.py")
    ap.add_argument("-o", "--output", default="map_topdown.png", help="Output PNG")
    args = ap.parse_args()

    xs, ys, names = [], [], []
    with open(args.csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                x = float(row["est_world_x"])
                y = float(row["est_world_y"])
            except (ValueError, KeyError):
                continue
            if x != x or y != y:
                continue
            xs.append(x)
            ys.append(y)
            names.append(row.get("name", ""))

    if not xs:
        print("No valid est_world_x/y rows.", file=sys.stderr)
        sys.exit(1)

    kinds = [object_kind(n) for n in names]
    uniq_kinds = sorted(set(kinds))
    fig, ax = plt.subplots(figsize=(9, 9), dpi=100)
    tc = np.asarray(plt.cm.tab20.colors)
    pal = tc[(np.arange(len(uniq_kinds)) % len(tc))]
    kind_to_c = {k: pal[i] for i, k in enumerate(uniq_kinds)}
    xs_a = np.asarray(xs, dtype=np.float64)
    ys_a = np.asarray(ys, dtype=np.float64)
    face = np.array(
        [to_rgba(kind_to_c.get(k, (0.5, 0.5, 0.5)))[:3] for k in kinds],
        dtype=np.float64,
    )
    # One scatter call: per-point scatter() is O(n) separate artists and is very slow.
    ax.scatter(
        xs_a,
        ys_a,
        c=face,
        s=12,
        alpha=0.7,
        edgecolors="none",
        rasterized=True,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("est_world_x (AirSim NED frame)")
    ax.set_ylabel("est_world_y")
    ax.grid(True, alpha=0.3)
    ax.set_title("Sparse object map (estimated world points)")

    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=kind_to_c[k],
            markersize=8,
            label=k,
        )
        for k in uniq_kinds
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8, ncol=1)

    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    print(
        "Wrote %s (%d points, %d mesh names, %d kinds in legend)"
        % (out, len(xs), len(set(names)), len(uniq_kinds))
    )


if __name__ == "__main__":
    main()
