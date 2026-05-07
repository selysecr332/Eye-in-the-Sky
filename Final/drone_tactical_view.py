"""
Drone Tactical View — live camera + AirSim mesh detection with a pilot-style HUD.

What find_things_cv.py does (for comparison):
  • Connects to AirSim (RPC), reads the front camera, asks Unreal for mesh-name
    detections (simGetDetections), optionally filters by color / sklearn, logs CSV,
    and can yaw the drone toward the largest box (NAV_TRACK).

What THIS file does:
  • Same detection pipeline, but paints a *tactical* overlay: artificial horizon,
    roll/pitch ladder, altitude & ground speed, FPS.
  • “Threat board” — detections sorted by 3D distance with color by range.
  • Mini radar — relative X/Y of targets in the camera frame (bird’s-eye widget).
  • Lock cue — chevron when the nearest target is near the optical center.
  • Persistent tracks with IDs + smoothing and lock confidence.
  • Engagement modes: nearest / largest / priority.
  • Detection source modes: AirSim / YOLO / Fusion.
  • Text query filter box for target intent (example: "red car").
  • Event CSV logging for target acquire/lock and mode changes.
  • Keys: q quit, c clear filters, a re-add filters, s save screenshot PNG,
    m cycle mode, d cycle detector, l toggle event logging,
    i edit query, Enter apply query, Backspace erase, Esc cancel edit,
    h show/hide query help box.

Run (Unreal in Play, same as find_things_cv.py):
  cd AirSim/PythonClient/detection
  python drone_tactical_view.py
"""

from __future__ import annotations

# --- msgpackrpc + Tornado 6 (same pattern as find_things_cv.py) ---
import sys
import os
import types


def _need_tornado6_compat():
    try:
        import tornado
        return getattr(tornado, "__version__", "0").startswith("6.")
    except Exception:
        return False


if _need_tornado6_compat():
    if "tornado.platform.auto" not in sys.modules:
        _auto = types.ModuleType("tornado.platform.auto")
        def _set_close_exec(fd):
            try:
                os.set_inheritable(fd, False)
            except (AttributeError, OSError):
                pass
        _auto.set_close_exec = _set_close_exec
        sys.modules["tornado.platform.auto"] = _auto
    import tornado.ioloop
    _RealPeriodicCallback = tornado.ioloop.PeriodicCallback
    class _PeriodicCallbackCompat(_RealPeriodicCallback):
        def __init__(self, callback, callback_time, _ioloop_ignored=None):
            super().__init__(callback, callback_time, jitter=0)
    tornado.ioloop.PeriodicCallback = _PeriodicCallbackCompat
    import tornado.iostream
    _RealIOStream = tornado.iostream.IOStream
    class _IOStreamCompat(_RealIOStream):
        def __init__(self, *args, **kwargs):
            kwargs.pop("io_loop", None)
            super().__init__(*args, **kwargs)
    tornado.iostream.IOStream = _IOStreamCompat
else:
    import tornado.ioloop  # noqa: F401
    import tornado.iostream  # noqa: F401

import math
import time
from datetime import datetime, timezone
import csv

import cv2
import numpy as np

import setup_path
import airsim  # noqa: E402
try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Tunables ---
AIRSIM_IP = "127.0.0.1"
AIRSIM_PORT = 41451
CAMERA_NAME = "0"
IMAGE_TYPE = airsim.ImageType.Scene
DETECTION_RADIUS_CM = 200 * 100

OBJECTS_TO_FIND = [
    "Car*", "House*", "Tree*", "Bench*", "Statue*", "Table*", "Cylinder*",
]

# Main video width after upscale; right column is added for HUD strip
MAIN_SCALE = 4
HUD_STRIP_W = 320
RADAR_SIZE = 200
RADAR_MAX_RANGE_M = 120.0

# Lock cue: fraction of half-frame width considered "centered"
LOCK_FRAC = 0.08

SHOT_DIR = os.path.join(SCRIPT_DIR, "tactical_screenshots")
EVENT_LOG_CSV = os.path.join(SCRIPT_DIR, "tactical_events.csv")

TRACK_MATCH_MAX_PX = 120.0
TRACK_MAX_MISS_SEC = 0.8
SMOOTH_ALPHA = 0.35
LOCK_CONFIRM_FRAMES = 6

ENGAGEMENT_MODES = ("nearest", "largest", "priority")
DETECTOR_MODES = ("airsim", "yolo", "fusion")
YOLO_MODEL_PATH = "yolov8n.pt"
YOLO_CONF = 0.35
YOLO_MAX_DET = 30
FUSION_IOU_MIN = 0.25
Y2R_SCALE_X_M = 80.0
Y2R_SCALE_Y_M = 60.0
COLOR_FRAC_MIN = 0.12
CLASS_ALIAS = {
    "car": ("car", "sedan", "vehicle"),
    "truck": ("truck", "lorry"),
    "bus": ("bus",),
    "person": ("person", "human", "man", "woman"),
    "bench": ("bench",),
    "tree": ("tree",),
    "house": ("house", "building"),
    "statue": ("statue",),
    "table": ("table",),
    "cylinder": ("cylinder",),
}
PRIORITY_WEIGHT = {
    "person": 100,
    "car": 90,
    "truck": 85,
    "van": 80,
    "bus": 75,
    "statue": 65,
    "cylinder": 60,
    "bench": 50,
    "house": 40,
    "tree": 20,
}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def _bgr_from_npng(png: np.ndarray) -> np.ndarray:
    if png is None:
        return None
    if len(png.shape) == 2:
        return cv2.cvtColor(png, cv2.COLOR_GRAY2BGR)
    if png.shape[2] == 4:
        return cv2.cvtColor(png, cv2.COLOR_BGRA2BGR)
    return png


def _euler_rpy_deg(q: airsim.Quaternionr) -> tuple[float, float, float]:
    """Roll, pitch, yaw (deg) from AirSim quaternion (w,x,y,z). UE-style."""
    w, x, y, z = q.w_val, q.x_val, q.y_val, q.z_val
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))
    sinp = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.degrees(math.asin(sinp))
    yaw = math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
    return roll, pitch, yaw


def _det_distance_m(det) -> float:
    p = det.relative_pose.position
    return math.sqrt(p.x_val * p.x_val + p.y_val * p.y_val + p.z_val * p.z_val)


def _range_color_m(d: float) -> tuple[int, int, int]:
    """BGR: cold (far) -> hot (close)."""
    if d > 80:
        return (255, 160, 80)
    if d > 40:
        return (80, 200, 255)
    if d > 15:
        return (80, 255, 180)
    return (80, 80, 255)


def _draw_horizon_ladder(
    img: np.ndarray,
    roll_deg: float,
    pitch_deg: float,
    cx: int,
    cy: int,
    radius: int,
) -> None:
    """Fake AI-style attitude ladder (small, top-left)."""
    overlay = img.copy()
    cv2.circle(overlay, (cx, cy), radius, (24, 24, 28), -1)
    cv2.circle(img, (cx, cy), radius, (90, 90, 100), 2)
    rad = math.radians(-roll_deg)
    pitch_px = int(np.clip(pitch_deg * 2.2, -radius + 8, radius - 8))
    for deg in (-20, -10, 0, 10, 20):
        off = int(deg * 2.2) - pitch_px
        if abs(off) > radius - 4:
            continue
        yl = cy + int(off * math.cos(rad))
        half = int((radius - 6) * math.cos(math.asin(np.clip(off / float(radius), -1.0, 1.0))))
        x0 = cx + int(-half * math.sin(rad))
        x1 = cx + int(half * math.sin(rad))
        y0 = cy + int(-half * math.cos(rad)) + int(off * math.sin(rad))
        y1 = y0
        cv2.line(overlay, (x0, y0), (x1, y1), (70, 200, 120), 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.55, img, 0.45, 0, dst=img)
    # Aircraft reference (fixed)
    cv2.line(img, (cx - 18, cy), (cx + 18, cy), (220, 220, 240), 2, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 4, (40, 180, 255), -1, cv2.LINE_AA)


def _draw_radar(
    panel: np.ndarray,
    items: list[dict],
    cx: int,
    cy: int,
    half: int,
    max_range: float,
) -> None:
    """Top-down: +Y forward in camera-relative frame (approx), X right."""
    cv2.circle(panel, (cx, cy), half, (40, 52, 40), 1, cv2.LINE_AA)
    for r in (0.25, 0.5, 0.75, 1.0):
        cv2.circle(panel, (cx, cy), int(half * r), (35, 45, 35), 1, cv2.LINE_AA)
    cv2.line(panel, (cx - half, cy), (cx + half, cy), (55, 65, 55), 1, cv2.LINE_AA)
    cv2.line(panel, (cx, cy - half), (cx, cy + half), (55, 65, 55), 1, cv2.LINE_AA)
    cv2.circle(panel, (cx, cy), 3, (200, 220, 200), -1, cv2.LINE_AA)
    for it in items:
        rx, ry = it["rx"], it["ry"]
        # Map ry as "ahead", rx as "right" (NaNs skipped)
        if not math.isfinite(rx) or not math.isfinite(ry):
            continue
        d = math.hypot(rx, ry)
        if d < 1e-6 or d > max_range * 1.5:
            continue
        t = min(1.0, d / max_range)
        px = cx + int((rx / max_range) * half * 0.92)
        py = cy - int((ry / max_range) * half * 0.92)
        px = int(np.clip(px, cx - half + 4, cx + half - 4))
        py = int(np.clip(py, cy - half + 4, cy + half - 4))
        col = _range_color_m(it["dist"])
        cv2.circle(panel, (px, py), 5, col, -1, cv2.LINE_AA)
        cv2.circle(panel, (px, py), 6, (20, 20, 20), 1, cv2.LINE_AA)


def _draw_lock_chevron(img: np.ndarray, w: int, h: int, cx_tgt: float, locked: bool) -> None:
    """Top-center chevron pointing toward target horizontal bearing."""
    tip_x = int(np.clip(cx_tgt, 20, w - 20))
    tip = (tip_x, 18)
    color = (80, 255, 120) if locked else (100, 180, 255)
    pts = np.array([[tip[0], tip[1]], [tip[0] - 10, tip[1] + 14], [tip[0] + 10, tip[1] + 14]], np.int32)
    cv2.fillConvexPoly(img, pts, color, cv2.LINE_AA)
    cv2.polylines(img, [pts], True, (30, 30, 30), 1, cv2.LINE_AA)


def _draw_query_input_box(img: np.ndarray, text_value: str, blink_on: bool = True) -> None:
    """
    Draw a centered modal-style query input box on top of the tactical frame.
    """
    h, w = img.shape[:2]
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w - 1, h - 1), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.28, img, 0.72, 0, img)

    box_w = int(min(1120, max(700, w * 0.78)))
    box_h = 190
    x0 = (w - box_w) // 2
    y0 = (h - box_h) // 2
    x1 = x0 + box_w
    y1 = y0 + box_h

    cv2.rectangle(img, (x0, y0), (x1, y1), (34, 38, 42), -1)
    cv2.rectangle(img, (x0, y0), (x1, y1), (92, 108, 124), 2)

    title = "Type what to find (example: red car)"
    cv2.putText(img, title, (x0 + 18, y0 + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (215, 225, 235), 1, cv2.LINE_AA)

    input_x0 = x0 + 14
    input_y0 = y0 + 56
    input_x1 = x1 - 14
    input_y1 = y1 - 50
    cv2.rectangle(img, (input_x0, input_y0), (input_x1, input_y1), (20, 24, 28), -1)
    cv2.rectangle(img, (input_x0, input_y0), (input_x1, input_y1), (120, 138, 154), 1)

    shown = text_value[-70:] if text_value else ""
    if blink_on:
        shown += "|"
    cv2.putText(
        img,
        shown if shown else "|",
        (input_x0 + 12, input_y0 + 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.86,
        (250, 252, 255),
        1,
        cv2.LINE_AA,
    )

    hint = "Enter: apply   Esc: cancel   Backspace: erase"
    cv2.putText(img, hint, (x0 + 18, y1 - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (170, 188, 204), 1, cv2.LINE_AA)


def _draw_query_help_box(img: np.ndarray) -> None:
    """
    Draw an on-screen help box listing valid query examples and aliases.
    """
    h, w = img.shape[:2]
    box_w = int(min(860, max(720, w * 0.56)))
    box_h = int(min(650, max(560, h * 0.80)))
    x0 = w - box_w - 16
    y0 = 18
    x1 = x0 + box_w
    y1 = y0 + box_h

    panel = img.copy()
    cv2.rectangle(panel, (x0, y0), (x1, y1), (18, 22, 26), -1)
    cv2.addWeighted(panel, 0.78, img, 0.22, 0, img)
    cv2.rectangle(img, (x0, y0), (x1, y1), (96, 118, 138), 2)

    lines = [
        "QUERY HELP (what you can enter)",
        "1) Class only",
        "(car) (person) (truck) (bus) (bench)",
        "(tree) (house) (statue) (table) (cylinder)",
        "2) Color only",
        "(red) (green) (blue) (yellow) (white) (black)",
        "3) Color + class (best)",
        "(red car) (blue car) (white bus)",
        "(black truck) (green tree)",
        "Aliases",
        "person: (human) (man) (woman)",
        "car: (vehicle) (sedan)",
        "truck: (lorry)   house: (building)",
        "Tip: use detector YOLO/FUSION for best query behavior.",
        "Press 'h' to hide/show this help.",
    ]

    yy = y0 + 30
    for i, line in enumerate(lines):
        col = (218, 234, 248) if i == 0 else (186, 205, 222)
        scale = 0.68 if i == 0 else 0.56
        cv2.putText(img, line, (x0 + 12, yy), cv2.FONT_HERSHEY_SIMPLEX, scale, col, 1, cv2.LINE_AA)
        yy += 36 if i == 0 else 33


def _calc_iou(a: dict, b: dict) -> float:
    ax0, ay0, ax1, ay1 = a["x0"], a["y0"], a["x1"], a["y1"]
    bx0, by0, bx1, by1 = b["x0"], b["y0"], b["x1"], b["y1"]
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    iw = max(0, ix1 - ix0)
    ih = max(0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    aa = max(1, (ax1 - ax0) * (ay1 - ay0))
    ba = max(1, (bx1 - bx0) * (by1 - by0))
    return float(inter) / float(aa + ba - inter)


def _pseudo_distance_from_area(area_px: float, frame_area_px: float) -> float:
    # Rough heuristic distance when no 3D pose is available (YOLO-only case).
    frac = max(1e-6, float(area_px) / float(max(1.0, frame_area_px)))
    d = 12.0 / math.sqrt(frac)
    return float(np.clip(d, 3.0, 160.0))


def _name_priority(name: str) -> int:
    s = name.lower()
    best = 0
    for k, w in PRIORITY_WEIGHT.items():
        if k in s:
            best = max(best, w)
    return best


def _parse_query(raw_query: str) -> dict:
    q = (raw_query or "").strip().lower()
    toks = [t for t in q.replace(",", " ").split() if t]
    color = None
    cls = None
    for t in toks:
        if t in ("red", "green", "blue", "yellow", "white", "black"):
            color = t
        # class alias resolution
        for canon, alias in CLASS_ALIAS.items():
            if t == canon or t in alias:
                cls = canon
                break
    return {"raw": q, "color": color, "class": cls}


def _color_fraction_bgr(roi_bgr: np.ndarray, color: str) -> float:
    if roi_bgr is None or roi_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    if color == "red":
        m1 = cv2.inRange(hsv, (0, 70, 40), (10, 255, 255))
        m2 = cv2.inRange(hsv, (170, 70, 40), (180, 255, 255))
        m = cv2.bitwise_or(m1, m2)
    elif color == "green":
        m = cv2.inRange(hsv, (35, 50, 40), (85, 255, 255))
    elif color == "blue":
        m = cv2.inRange(hsv, (90, 50, 40), (130, 255, 255))
    elif color == "yellow":
        m = cv2.inRange(hsv, (18, 60, 40), (35, 255, 255))
    elif color == "white":
        m = cv2.inRange(hsv, (0, 0, 180), (180, 45, 255))
    elif color == "black":
        m = cv2.inRange(hsv, (0, 0, 0), (180, 255, 45))
    else:
        return 0.0
    return float(np.count_nonzero(m)) / float(max(1, m.size))


def _class_match(name: str, class_query: str | None) -> bool:
    if not class_query:
        return True
    s = (name or "").lower()
    alias = CLASS_ALIAS.get(class_query, (class_query,))
    return any(a in s for a in alias) or class_query in s


def _filter_items_by_query(items: list[dict], frame_bgr: np.ndarray, query_spec: dict) -> list[dict]:
    if not items:
        return items
    color_q = query_spec.get("color")
    class_q = query_spec.get("class")
    raw_q = query_spec.get("raw", "")
    if not raw_q:
        return items

    h, w = frame_bgr.shape[:2]
    out = []
    for it in items:
        if not _class_match(it.get("name", ""), class_q):
            continue
        if color_q:
            x0 = int(np.clip(it["x0"], 0, w - 1))
            y0 = int(np.clip(it["y0"], 0, h - 1))
            x1 = int(np.clip(it["x1"], 0, w - 1))
            y1 = int(np.clip(it["y1"], 0, h - 1))
            if x1 <= x0 or y1 <= y0:
                continue
            roi = frame_bgr[y0:y1, x0:x1]
            frac = _color_fraction_bgr(roi, color_q)
            it["color_frac"] = frac
            if frac < COLOR_FRAC_MIN:
                continue
        out.append(it)
    return out


def _log_event(writer, event_name: str, frame_idx: int, mode: str, target: dict | None, extra: str = "") -> None:
    if writer is None:
        return
    now = datetime.now(timezone.utc).isoformat()
    tid = -1
    tname = ""
    dist = float("nan")
    if target is not None:
        tid = int(target.get("id", -1))
        tname = str(target.get("name", ""))
        dist = float(target.get("dist", float("nan")))
    writer.writerow([now, frame_idx, event_name, mode, tid, tname, dist, extra])


def _update_tracks(tracks: dict, items: list[dict], now_t: float, next_id: int) -> int:
    """
    Greedy nearest-center association + exponential smoothing.
    Mutates items by adding 'id', 'stable', 'lock_ratio', 'lock_frames'.
    """
    assigned = set()
    track_ids = list(tracks.keys())
    for it in items:
        cx, cy = it["cx"], it["cy"]
        best_tid = None
        best_d = 1e18
        for tid in track_ids:
            if tid in assigned:
                continue
            tr = tracks[tid]
            dt = now_t - tr["last_t"]
            if dt > TRACK_MAX_MISS_SEC:
                continue
            # Soft class consistency: prefer same semantic label.
            this_tok = str(it["name"]).split("_")[0].lower() if str(it["name"]) else ""
            class_pen = 0.0 if this_tok and this_tok in tr["name"].lower() else 12.0
            dd = math.hypot(cx - tr["u"], cy - tr["v"]) + class_pen
            if dd < best_d and dd <= TRACK_MATCH_MAX_PX:
                best_d = dd
                best_tid = tid

        if best_tid is None:
            tid = next_id
            next_id += 1
            tracks[tid] = {
                "id": tid,
                "u": float(cx),
                "v": float(cy),
                "dist": float(it["dist"]),
                "rx": float(it["rx"]),
                "ry": float(it["ry"]),
                "name": str(it["name"]),
                "hits": 1,
                "last_t": now_t,
                "misses": 0,
                "lock_frames": 0,
            }
            it["id"] = tid
        else:
            assigned.add(best_tid)
            tr = tracks[best_tid]
            tr["u"] = (1.0 - SMOOTH_ALPHA) * tr["u"] + SMOOTH_ALPHA * float(cx)
            tr["v"] = (1.0 - SMOOTH_ALPHA) * tr["v"] + SMOOTH_ALPHA * float(cy)
            tr["dist"] = (1.0 - SMOOTH_ALPHA) * tr["dist"] + SMOOTH_ALPHA * float(it["dist"])
            tr["rx"] = (1.0 - SMOOTH_ALPHA) * tr["rx"] + SMOOTH_ALPHA * float(it["rx"])
            tr["ry"] = (1.0 - SMOOTH_ALPHA) * tr["ry"] + SMOOTH_ALPHA * float(it["ry"])
            tr["name"] = str(it["name"])
            tr["hits"] += 1
            tr["last_t"] = now_t
            tr["misses"] = 0
            it["id"] = best_tid

        # Mirror smoothed track state into this frame item.
        tr = tracks[it["id"]]
        it["cx"] = tr["u"]
        it["cy"] = tr["v"]
        it["dist"] = tr["dist"]
        it["rx"] = tr["rx"]
        it["ry"] = tr["ry"]
        it["name"] = tr["name"]
        it["stable"] = tr["hits"] >= 5
        it["lock_frames"] = tr["lock_frames"]
        it["lock_ratio"] = min(1.0, tr["lock_frames"] / float(max(1, tr["hits"])))

    # Age and prune stale tracks.
    kill_ids = []
    matched_ids = {it["id"] for it in items if "id" in it}
    for tid, tr in tracks.items():
        if tid not in matched_ids:
            tr["misses"] += 1
        if now_t - tr["last_t"] > TRACK_MAX_MISS_SEC:
            kill_ids.append(tid)
    for tid in kill_ids:
        tracks.pop(tid, None)

    return next_id


def _pick_primary_target(items: list[dict], mode: str):
    if not items:
        return None
    if mode == "nearest":
        return min(items, key=lambda x: x["dist"])
    if mode == "largest":
        return max(items, key=lambda x: x["area"])
    # priority
    def _score(it):
        # Higher is better; prefer semantic priority, then close, then larger.
        pr = _name_priority(it["name"])
        return (pr * 1000.0) + (200.0 - min(200.0, float(it["dist"]))) + math.log1p(max(1.0, float(it["area"])))

    return max(items, key=_score)


def _build_items_airsim(detections):
    items = []
    for det in detections:
        x0 = int(det.box2D.min.x_val)
        y0 = int(det.box2D.min.y_val)
        x1 = int(det.box2D.max.x_val)
        y1 = int(det.box2D.max.y_val)
        name = str(getattr(det, "name", ""))
        d = _det_distance_m(det)
        rp = det.relative_pose.position
        rx, ry, rz = rp.x_val, rp.y_val, rp.z_val
        cx = 0.5 * (x0 + x1)
        cy = 0.5 * (y0 + y1)
        items.append({
            "det": det, "name": name, "source": "airsim",
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "dist": d, "rx": rx, "ry": ry, "rz": rz,
            "cx": cx, "cy": cy, "area": max(0, x1 - x0) * max(0, y1 - y0),
        })
    return items


def _build_items_yolo(model, bgr: np.ndarray):
    if model is None:
        return []
    h0, w0 = bgr.shape[:2]
    frame_area = float(max(1, h0 * w0))
    out = []
    try:
        result = model.predict(source=bgr, verbose=False, conf=YOLO_CONF, max_det=YOLO_MAX_DET)[0]
        names = result.names if hasattr(result, "names") else {}
        boxes = result.boxes
        if boxes is None:
            return []
        for b in boxes:
            xyxy = b.xyxy[0].tolist()
            x0, y0, x1, y1 = [int(v) for v in xyxy]
            cls_id = int(b.cls[0].item()) if b.cls is not None else -1
            conf = float(b.conf[0].item()) if b.conf is not None else float("nan")
            cls_name = str(names.get(cls_id, f"class_{cls_id}"))
            area = max(0, x1 - x0) * max(0, y1 - y0)
            cx = 0.5 * (x0 + x1)
            cy = 0.5 * (y0 + y1)
            # Approximate radar position from image-center offset.
            rx = ((cx / max(1.0, w0)) - 0.5) * Y2R_SCALE_X_M
            ry = (0.5 - (cy / max(1.0, h0))) * Y2R_SCALE_Y_M
            out.append({
                "det": None, "name": cls_name, "source": "yolo",
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "dist": _pseudo_distance_from_area(area, frame_area),
                "rx": rx, "ry": ry, "rz": 0.0,
                "cx": cx, "cy": cy, "area": area,
                "conf": conf,
            })
    except Exception:
        return []
    return out


def _fuse_items(airsim_items: list[dict], yolo_items: list[dict]) -> list[dict]:
    if not yolo_items:
        return list(airsim_items)
    fused = []
    used_air = set()
    for yi in yolo_items:
        best_j = -1
        best_iou = 0.0
        for j, ai in enumerate(airsim_items):
            iou = _calc_iou(yi, ai)
            if iou > best_iou:
                best_iou = iou
                best_j = j
        if best_j >= 0 and best_iou >= FUSION_IOU_MIN:
            ai = airsim_items[best_j]
            used_air.add(best_j)
            merged = dict(yi)
            merged["dist"] = ai["dist"]
            merged["rx"] = ai["rx"]
            merged["ry"] = ai["ry"]
            merged["rz"] = ai["rz"]
            merged["source"] = "fusion"
            merged["name"] = yi["name"]
            fused.append(merged)
        else:
            yi2 = dict(yi)
            yi2["source"] = "yolo"
            fused.append(yi2)
    for j, ai in enumerate(airsim_items):
        if j not in used_air:
            ai2 = dict(ai)
            ai2["source"] = "airsim"
            fused.append(ai2)
    return fused


def main():
    _log("Connecting to AirSim at %s:%s ..." % (AIRSIM_IP, AIRSIM_PORT))
    client = airsim.MultirotorClient(ip=AIRSIM_IP, port=AIRSIM_PORT, timeout_value=60)
    try:
        client.confirmConnection()
        _log("Connected.")
    except Exception as e:
        _log("Connection failed: %s" % e)
        _log("Start Unreal in Play with AirSimGameMode, then retry.")
        sys.exit(1)

    try:
        client.simClearDetectionMeshNames(CAMERA_NAME, IMAGE_TYPE)
    except Exception:
        pass
    client.simSetDetectionFilterRadius(CAMERA_NAME, IMAGE_TYPE, DETECTION_RADIUS_CM)
    for name in OBJECTS_TO_FIND:
        try:
            client.simAddDetectionFilterMeshName(CAMERA_NAME, IMAGE_TYPE, name)
        except Exception as e:
            _log("Filter %r skipped: %s" % (name, e))

    os.makedirs(SHOT_DIR, exist_ok=True)
    win = "Drone Tactical View (q quit | c clear | a add | s shot | m mode | d detector | l log)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    prev_pos = None
    prev_t = time.time()
    ema_fps = 0.0
    _frame = 0
    tracks = {}
    next_track_id = 1
    mode_idx = 0
    current_mode = ENGAGEMENT_MODES[mode_idx]
    det_mode_idx = 0
    current_det_mode = DETECTOR_MODES[det_mode_idx]
    query_text = ""
    query_spec = _parse_query(query_text)
    query_edit = False
    query_buffer = ""
    show_query_help = True
    event_logging_enabled = True
    last_primary_id = None
    last_locked = False
    yolo_notified_missing = False

    yolo_model = None
    yolo_ready = False
    if YOLO is not None:
        try:
            yolo_model = YOLO(YOLO_MODEL_PATH)
            yolo_ready = True
            _log("YOLO ready: %s" % YOLO_MODEL_PATH)
        except Exception as e:
            _log("YOLO disabled (load failed): %s" % e)
            yolo_model = None
            yolo_ready = False
    else:
        _log("YOLO disabled: ultralytics not installed.")

    csv_fp = None
    csv_writer = None
    try:
        csv_exists = os.path.isfile(EVENT_LOG_CSV)
        csv_fp = open(EVENT_LOG_CSV, "a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_fp)
        if not csv_exists:
            csv_writer.writerow(["utc_time", "frame", "event", "mode", "track_id", "name", "distance_m", "extra"])
        _log("Event log: %s" % EVENT_LOG_CSV)
    except Exception as e:
        _log("Event log disabled: %s" % e)
        csv_fp = None
        csv_writer = None

    _log("HUD running. Filters: %s" % OBJECTS_TO_FIND)
    _log("Mode: %s" % current_mode)
    _log("Detector: %s" % current_det_mode)
    _log("Query: (none)")
    _log_event(csv_writer if event_logging_enabled else None, "session_start", _frame, current_mode, None)

    while True:
        t0 = time.time()
        _frame += 1
        raw = client.simGetImage(CAMERA_NAME, IMAGE_TYPE)
        if not raw:
            continue
        png = cv2.imdecode(airsim.string_to_uint8_array(raw), cv2.IMREAD_UNCHANGED)
        bgr = _bgr_from_npng(png)
        if bgr is None:
            continue

        h0, w0 = bgr.shape[:2]
        scene = cv2.resize(bgr, (w0 * MAIN_SCALE, h0 * MAIN_SCALE), interpolation=cv2.INTER_LINEAR)
        H, W = scene.shape[:2]

        try:
            state = client.getMultirotorState()
            pos = state.kinematics_estimated.position
            q = state.kinematics_estimated.orientation
            roll_deg, pitch_deg, yaw_deg = _euler_rpy_deg(q)
            alt = -pos.z_val
            vx = vy = speed = 0.0
            if prev_pos is not None:
                dt = max(1e-3, t0 - prev_t)
                vx = (pos.x_val - prev_pos[0]) / dt
                vy = (pos.y_val - prev_pos[1]) / dt
                speed = math.hypot(vx, vy)
            prev_pos = (pos.x_val, pos.y_val, pos.z_val)
            prev_t = t0
        except Exception:
            roll_deg = pitch_deg = yaw_deg = 0.0
            alt = speed = float("nan")

        detections = client.simGetDetections(CAMERA_NAME, IMAGE_TYPE) or []
        airsim_items = _build_items_airsim(detections)
        yolo_items = _build_items_yolo(yolo_model, bgr) if (current_det_mode in ("yolo", "fusion") and yolo_ready) else []

        if current_det_mode == "airsim":
            items = airsim_items
        elif current_det_mode == "yolo":
            if yolo_ready:
                items = yolo_items
            else:
                items = airsim_items
                if not yolo_notified_missing:
                    _log("Detector fallback: YOLO unavailable -> AirSim.")
                    yolo_notified_missing = True
        else:  # fusion
            if yolo_ready:
                items = _fuse_items(airsim_items, yolo_items)
            else:
                items = airsim_items
                if not yolo_notified_missing:
                    _log("Detector fallback: Fusion requested but YOLO unavailable -> AirSim.")
                    yolo_notified_missing = True

        items = _filter_items_by_query(items, bgr, query_spec)

        next_track_id = _update_tracks(tracks, items, t0, next_track_id)
        items.sort(key=lambda x: x["dist"])
        primary = _pick_primary_target(items, current_mode)

        for it in items:
            col = _range_color_m(it["dist"])
            x0, y0, x1, y1 = it["x0"], it["y0"], it["x1"], it["y1"]
            xs0, ys0 = x0 * MAIN_SCALE, y0 * MAIN_SCALE
            xs1, ys1 = x1 * MAIN_SCALE, y1 * MAIN_SCALE
            cv2.rectangle(scene, (int(xs0), int(ys0)), (int(xs1), int(ys1)), col, 2, cv2.LINE_AA)
            if it is primary:
                cv2.rectangle(scene, (int(xs0) - 2, int(ys0) - 2), (int(xs1) + 2, int(ys1) + 2), (60, 255, 255), 1, cv2.LINE_AA)
            stable_tag = "S" if it.get("stable", False) else "~"
            src_tag = it.get("source", "air")[0].upper()
            conf = float(it.get("conf", float("nan")))
            conf_tag = "" if not math.isfinite(conf) else (" c%.2f" % conf)
            label = "#%d %s%s %s %.0fm%s" % (it.get("id", -1), stable_tag, src_tag, it["name"][:14], it["dist"], conf_tag)
            cv2.putText(scene, label, (int(xs0), max(18, int(ys0) - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)

        locked = False
        if primary is not None:
            err = abs(primary["cx"] - 0.5 * w0) / max(0.5 * w0, 1.0)
            locked = err < LOCK_FRAC
            _draw_lock_chevron(scene, W, H, primary["cx"] * MAIN_SCALE, locked)
            tr = tracks.get(primary.get("id"))
            if tr is not None:
                tr["lock_frames"] = tr["lock_frames"] + 1 if locked else max(0, tr["lock_frames"] - 1)
                primary["lock_frames"] = tr["lock_frames"]
                primary["lock_ratio"] = min(1.0, tr["lock_frames"] / float(max(1, tr["hits"])))

        if primary is not None and primary.get("id") != last_primary_id:
            _log_event(
                csv_writer if event_logging_enabled else None,
                "target_acquired",
                _frame,
                current_mode,
                primary,
                "switch",
            )
            last_primary_id = primary.get("id")
        if locked and not last_locked and primary is not None and primary.get("lock_frames", 0) >= LOCK_CONFIRM_FRAMES:
            _log_event(csv_writer if event_logging_enabled else None, "lock_on", _frame, current_mode, primary)
        if (not locked) and last_locked:
            _log_event(csv_writer if event_logging_enabled else None, "lock_lost", _frame, current_mode, primary)
        last_locked = locked

        dt_tick = max(1e-3, time.time() - t0)
        inst_fps = 1.0 / dt_tick
        ema_fps = 0.92 * ema_fps + 0.08 * inst_fps if ema_fps > 0 else inst_fps

        _draw_horizon_ladder(scene, roll_deg, pitch_deg, 72, 72, 58)

        hud = np.zeros((H, HUD_STRIP_W, 3), dtype=np.uint8)
        hud[:] = (28, 32, 36)

        y = 22
        def hud_line(txt, col=(220, 235, 245)):
            nonlocal y
            cv2.putText(hud, txt, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1, cv2.LINE_AA)
            y += 20

        hud_line("DRONE TACTICAL VIEW", (180, 230, 255))
        hud_line("FPS %.0f  |  frames %d" % (ema_fps, _frame), (160, 200, 160))
        hud_line("MODE %s" % current_mode.upper(), (255, 220, 120))
        hud_line("DET-SRC %s%s" % (current_det_mode.upper(), "" if yolo_ready else " (YOLO off)"), (220, 205, 160))
        q_disp = query_buffer if query_edit else query_text
        q_disp = q_disp if q_disp else "(none)"
        hud_line("QUERY %s%s" % ("[edit] " if query_edit else "", q_disp[:26]), (240, 220, 160) if query_edit else (190, 200, 215))
        hud_line("YAW %5.1f  ROLL %4.1f" % (yaw_deg, roll_deg), (200, 210, 220))
        hud_line("PITCH %5.1f" % pitch_deg, (200, 210, 220))
        if math.isfinite(alt):
            hud_line("ALT  %.1f m (NED -Z)" % alt, (140, 200, 255))
        if math.isfinite(speed):
            hud_line("GND  %.1f m/s" % speed, (160, 220, 200))
        hud_line("DET  %d targets | tracks %d" % (len(items), len(tracks)), (220, 200, 140))
        hud_line("LOG  %s" % ("ON" if event_logging_enabled else "OFF"), (180, 220, 180) if event_logging_enabled else (180, 180, 180))

        y += 6
        cv2.line(hud, (8, y), (HUD_STRIP_W - 8, y), (60, 70, 75), 1)
        y += 16
        hud_line("THREAT BOARD (by range)", (200, 200, 255))

        for i, it in enumerate(items[:12]):
            short = ("%s" % it["name"])[:18]
            prio = _name_priority(it["name"])
            marker = ">" if (primary is not None and it.get("id") == primary.get("id")) else " "
            lockp = int(100.0 * it.get("lock_ratio", 0.0))
            line = "%s#%02d %4.0fm L%02d P%02d %s" % (marker, it.get("id", 0), it["dist"], lockp, prio, short)
            hud_line(line, (80, 240, 240) if marker == ">" else _range_color_m(it["dist"]))

        rcx, rcy = HUD_STRIP_W // 2, H - RADAR_SIZE // 2 - 24
        _draw_radar(hud, items, rcx, rcy, RADAR_SIZE // 2, RADAR_MAX_RANGE_M)
        cv2.putText(hud, "RADAR (rel X/Y, m)", (12, H - RADAR_SIZE - 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 190, 200), 1, cv2.LINE_AA)

        composite = np.hstack([scene, hud])

        bar = "T:%d | ACTIVE:%s" % (
            len(items),
            "none" if primary is None else ("#%d %.0fm %s" % (primary.get("id", -1), primary["dist"], primary["name"][:16])),
        )
        bar_col = (80, 255, 120) if locked else (100, 190, 255)
        cv2.putText(composite, bar, (12, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, bar_col, 2, cv2.LINE_AA)

        # Query helper line
        helper = "i:edit query | Enter:apply | Backspace:erase | Esc:cancel edit | h:help"
        cv2.putText(composite, helper, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 200, 220), 1, cv2.LINE_AA)
        if query_edit:
            blink_on = (int(time.time() * 2.0) % 2) == 0
            _draw_query_input_box(composite, query_buffer, blink_on=blink_on)
        if show_query_help:
            _draw_query_help_box(composite)

        cv2.imshow(win, composite)
        key = cv2.waitKey(1) & 0xFF
        if key == 255:
            continue
        if query_edit:
            if key in (13, 10):  # Enter
                query_text = query_buffer.strip()
                query_spec = _parse_query(query_text)
                query_edit = False
                _log("Query -> %s" % (query_text if query_text else "(none)"))
                _log_event(csv_writer if event_logging_enabled else None, "query_change", _frame, current_mode, primary, query_text)
                continue
            if key == 27:  # Esc
                query_edit = False
                continue
            if key in (8, 127):  # Backspace / DEL
                query_buffer = query_buffer[:-1]
                continue
            if 32 <= key <= 126:
                query_buffer += chr(key)
                continue

        if key == ord("q"):
            break
        if key == ord("c"):
            client.simClearDetectionMeshNames(CAMERA_NAME, IMAGE_TYPE)
            _log("Cleared detection filters.")
        elif key == ord("a"):
            for name in OBJECTS_TO_FIND:
                try:
                    client.simAddDetectionFilterMeshName(CAMERA_NAME, IMAGE_TYPE, name)
                except Exception:
                    pass
            _log("Re-added filters.")
        elif key == ord("s"):
            fn = os.path.join(SHOT_DIR, "tactical_%s.png" % _utc_iso())
            cv2.imwrite(fn, composite)
            _log("Saved %s" % fn)
            _log_event(csv_writer if event_logging_enabled else None, "snapshot", _frame, current_mode, primary, fn)
        elif key == ord("m"):
            mode_idx = (mode_idx + 1) % len(ENGAGEMENT_MODES)
            current_mode = ENGAGEMENT_MODES[mode_idx]
            _log("Mode -> %s" % current_mode)
            _log_event(csv_writer if event_logging_enabled else None, "mode_change", _frame, current_mode, primary, current_det_mode)
        elif key == ord("d"):
            det_mode_idx = (det_mode_idx + 1) % len(DETECTOR_MODES)
            current_det_mode = DETECTOR_MODES[det_mode_idx]
            _log("Detector -> %s" % current_det_mode)
            _log_event(csv_writer if event_logging_enabled else None, "detector_change", _frame, current_mode, primary, current_det_mode)
        elif key == ord("l"):
            event_logging_enabled = not event_logging_enabled
            _log("Event logging -> %s" % ("ON" if event_logging_enabled else "OFF"))
            _log_event(csv_writer if event_logging_enabled else None, "logging_toggle", _frame, current_mode, primary, str(event_logging_enabled))
        elif key == ord("i"):
            query_edit = True
            query_buffer = query_text
            _log("Query edit mode: type text, Enter to apply.")
        elif key == ord("h"):
            show_query_help = not show_query_help
            _log("Query help -> %s" % ("ON" if show_query_help else "OFF"))

    cv2.destroyAllWindows()
    _log_event(csv_writer if event_logging_enabled else None, "session_end", _frame, current_mode, None)
    if csv_fp is not None:
        csv_fp.close()


if __name__ == "__main__":
    main()
