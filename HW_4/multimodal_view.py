"""
HW_4 — RGB + infrared side-by side, 2D motion trails, optional CSV log.

Run (from repo root Drons):
  .\\AirSim\\PythonClient\\detection\\venv310\\Scripts\\python.exe ALL_HW\\HW_4\\multimodal_view.py
  .\\AirSim\\PythonClient\\detection\\venv310\\Scripts\\python.exe ALL_HW\\HW_4\\multimodal_view.py --csv ALL_HW\\HW_4\\trails_log.csv

Keys: q quit | c clear detection filters | a re-add filters | t toggle IR false-color
"""

from __future__ import print_function

import argparse
import csv
import math
import os
import sys
import time
from collections import deque

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYCLIENT = os.path.join(ROOT, "AirSim", "PythonClient")
if PYCLIENT not in sys.path:
    sys.path.insert(0, PYCLIENT)

import airsim  # noqa: E402

AIRSIM_IP = "127.0.0.1"
AIRSIM_PORT = 41451
CAMERA_NAME = "0"
IMG_SCENE = airsim.ImageType.Scene
IMG_IR = airsim.ImageType.Infrared
DETECTION_RADIUS_CM = 200 * 100
WINDOW = "HW_4 multimodal — Scene | IR"

DEFAULT_OBJECTS_TO_FIND = [
    "Car*",
    "House*",
    "Small*",
    "Tree*",
    "Bench*",
    "Birch*",
    "Medium*",
]


def objects_to_find():
    env = os.environ.get("AIRSIM_DETECT_FILTERS", "").strip()
    if not env:
        return list(DEFAULT_OBJECTS_TO_FIND)
    parts = [p.strip() for p in env.split(",") if p.strip()]
    return parts if parts else list(DEFAULT_OBJECTS_TO_FIND)


def log(msg):
    print(msg, flush=True)


def decode_image(raw, flags):
    if not raw:
        return None
    return cv2.imdecode(airsim.string_to_uint8_array(raw), flags)


def setup_filters(client, patterns):
    client.simClearDetectionMeshNames(CAMERA_NAME, IMG_SCENE)
    client.simSetDetectionFilterRadius(CAMERA_NAME, IMG_SCENE, DETECTION_RADIUS_CM)
    for p in patterns:
        client.simAddDetectionFilterMeshName(CAMERA_NAME, IMG_SCENE, p)


def measurements_from_detections(detections):
    out = []
    for det in detections:
        x0 = float(det.box2D.min.x_val)
        y0 = float(det.box2D.min.y_val)
        x1 = float(det.box2D.max.x_val)
        y1 = float(det.box2D.max.y_val)
        out.append(
            {
                "name": str(det.name),
                "u": 0.5 * (x0 + x1),
                "v": 0.5 * (y0 + y1),
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
            }
        )
    return out


def match_greedy(tracks, meas, max_dist):
    """Return list of (track_index, meas_index) for nearest pairs under max_dist."""
    pairs = []
    used_t = set()
    for mi, m in enumerate(meas):
        best_ti = None
        best_d = max_dist
        for ti, tr in enumerate(tracks):
            if ti in used_t:
                continue
            d = math.hypot(m["u"] - tr["u"], m["v"] - tr["v"])
            if d < best_d:
                best_d = d
                best_ti = ti
        if best_ti is not None:
            pairs.append((best_ti, mi))
            used_t.add(best_ti)
    return pairs


def prepare_ir_display(ir_bgr, target_h, colorize):
    if ir_bgr is None:
        panel = (target_h, 320, 3)
        img = np.zeros(panel, dtype=np.uint8)
        cv2.putText(img, "No IR image", (10, target_h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
        return img
    if ir_bgr.shape[0] != target_h:
        scale = target_h / float(ir_bgr.shape[0])
        ir_bgr = cv2.resize(
            ir_bgr,
            (int(ir_bgr.shape[1] * scale), target_h),
            interpolation=cv2.INTER_LINEAR,
        )
    if colorize:
        gray = cv2.cvtColor(ir_bgr, cv2.COLOR_BGR2GRAY)
        return cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
    return ir_bgr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="", help="Append centroid / track CSV")
    ap.add_argument("--trail-len", type=int, default=40)
    ap.add_argument("--match-dist", type=float, default=90.0)
    args = ap.parse_args()

    patterns = objects_to_find()
    client = airsim.MultirotorClient(ip=AIRSIM_IP, port=AIRSIM_PORT, timeout_value=60)
    client.confirmConnection()
    setup_filters(client, patterns)
    log("Filters: %s" % patterns)

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)

    csv_file = None
    csv_writer = None
    if args.csv:
        path = os.path.abspath(args.csv)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        new_file = not os.path.isfile(path)
        csv_file = open(path, "a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        if new_file:
            csv_writer.writerow(
                ["unix_time", "track_id", "name", "u", "v", "n_detections"]
            )
        log("CSV log: %s" % path)

    tracks = []
    next_tid = 0
    ir_colorize = True
    log("Keys: q quit | c clear filters | a re-add | t IR colormap")

    try:
        while True:
            raw_rgb = client.simGetImage(CAMERA_NAME, IMG_SCENE)
            raw_ir = client.simGetImage(CAMERA_NAME, IMG_IR)
            rgb = decode_image(raw_rgb, cv2.IMREAD_COLOR)
            ir_raw = decode_image(raw_ir, cv2.IMREAD_COLOR)
            if rgb is None:
                continue

            detections = client.simGetDetections(CAMERA_NAME, IMG_SCENE) or []
            meas = measurements_from_detections(detections)

            pairs = match_greedy(tracks, meas, args.match_dist)
            new_tracks = []

            for ti, mi in pairs:
                m = meas[mi]
                tr = tracks[ti]
                tr["u"] = m["u"]
                tr["v"] = m["v"]
                tr["name"] = m["name"]
                tr["trail"].append((int(m["u"]), int(m["v"])))
                new_tracks.append(tr)
                if csv_writer:
                    csv_writer.writerow(
                        [
                            "%.6f" % time.time(),
                            tr["id"],
                            m["name"],
                            "%.2f" % m["u"],
                            "%.2f" % m["v"],
                            len(detections),
                        ]
                    )

            unmatched_mi = set(range(len(meas))) - {mi for _, mi in pairs}
            for mi in unmatched_mi:
                m = meas[mi]
                tr = {
                    "id": next_tid,
                    "u": m["u"],
                    "v": m["v"],
                    "name": m["name"],
                    "trail": deque(maxlen=args.trail_len),
                }
                tr["trail"].append((int(m["u"]), int(m["v"])))
                new_tracks.append(tr)
                next_tid += 1
                if csv_writer:
                    csv_writer.writerow(
                        [
                            "%.6f" % time.time(),
                            tr["id"],
                            m["name"],
                            "%.2f" % m["u"],
                            "%.2f" % m["v"],
                            len(detections),
                        ]
                    )

            tracks = new_tracks
            if csv_file:
                csv_file.flush()

            vis = rgb.copy()
            for m in meas:
                x0, y0, x1, y1 = int(m["x0"]), int(m["y0"]), int(m["x1"]), int(m["y1"])
                cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 0), 2)
                cv2.putText(
                    vis,
                    m["name"],
                    (x0, max(18, y0 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 255, 0),
                    1,
                    cv2.LINE_AA,
                )

            for tr in tracks:
                pts = list(tr["trail"])
                for k in range(1, len(pts)):
                    thickness = 1 + k // 10
                    cv2.line(vis, pts[k - 1], pts[k], (255, 128, 0), min(thickness, 4), cv2.LINE_AA)
                if pts:
                    cv2.circle(vis, pts[-1], 4, (0, 165, 255), -1)

            h = vis.shape[0]
            ir_panel = prepare_ir_display(ir_raw, h, ir_colorize)
            if ir_panel.shape[1] != vis.shape[1]:
                scale = vis.shape[1] / float(ir_panel.shape[1])
                ir_panel = cv2.resize(
                    ir_panel,
                    (vis.shape[1], h),
                    interpolation=cv2.INTER_LINEAR,
                )

            combo = np.hstack([vis, ir_panel])
            cv2.putText(
                combo,
                "Scene + trails | IR",
                (10, 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                combo,
                "Seen: %d  tracks: %d" % (len(meas), len(tracks)),
                (10, 56),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (200, 255, 200),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow(WINDOW, combo)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                client.simClearDetectionMeshNames(CAMERA_NAME, IMG_SCENE)
                log("Filters cleared")
            if key == ord("a"):
                setup_filters(client, patterns)
                log("Filters restored")
            if key == ord("t"):
                ir_colorize = not ir_colorize
                log("IR colorize = %s" % ir_colorize)
    finally:
        if csv_file:
            csv_file.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
