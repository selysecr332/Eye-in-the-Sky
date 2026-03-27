"""
HW_5 — Log detection positions for sparse mapping (world-frame estimate + geo).

Uses:
- simGetDetections(Scene) for names, box2D, relative_pose, geo_point
- simGetCameraInfo for camera pose in world (NED in AirSim)
- Rough estimate: P_world ≈ R_cam * P_rel + t_cam

Assumption documented in HW_5 README: relative_pose.position is expressed in the
camera optical frame; verify against your AirSim / UE version if points look wrong.

Run:
  .\\AirSim\\PythonClient\\detection\\venv310\\Scripts\\python.exe ALL_HW\\HW_5\\world_map_points.py --csv ALL_HW\\HW_5\\map_points.csv

Keys: q quit | c clear filters | a re-add
"""

from __future__ import print_function

import argparse
import csv
import os
import sys
import time

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
DETECTION_RADIUS_CM = 200 * 100

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


def setup_filters(client, patterns):
    client.simClearDetectionMeshNames(CAMERA_NAME, IMG_SCENE)
    client.simSetDetectionFilterRadius(CAMERA_NAME, IMG_SCENE, DETECTION_RADIUS_CM)
    for p in patterns:
        client.simAddDetectionFilterMeshName(CAMERA_NAME, IMG_SCENE, p)


def quat_to_R(q):
    """Quaternionr w,x,y,z → 3x3 rotation matrix (unit quaternion)."""
    w, x, y, z = q.w_val, q.x_val, q.y_val, q.z_val
    n = w * w + x * x + y * y + z * z
    if n < 1e-12:
        return np.eye(3)
    s = 2.0 / n
    wx, wy, wz = s * w * x, s * w * y, s * w * z
    xx, xy, xz = s * x * x, s * x * y, s * x * z
    yy, yz, zz = s * y * y, s * y * z, s * z * z
    return np.array(
        [
            [1.0 - (yy + zz), xy - wz, xz + wy],
            [xy + wz, 1.0 - (xx + zz), yz - wx],
            [xz - wy, yz + wx, 1.0 - (xx + yy)],
        ],
        dtype=np.float64,
    )


def est_world_from_detection(cam_pose, det):
    R = quat_to_R(cam_pose.orientation)
    t = np.array(
        [cam_pose.position.x_val, cam_pose.position.y_val, cam_pose.position.z_val],
        dtype=np.float64,
    )
    p = det.relative_pose.position
    v = np.array([p.x_val, p.y_val, p.z_val], dtype=np.float64)
    world = R.dot(v) + t
    return world, t, R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Output CSV path")
    ap.add_argument("--interval", type=float, default=0.2, help="Seconds between log samples")
    args = ap.parse_args()

    patterns = objects_to_find()
    client = airsim.MultirotorClient(ip=AIRSIM_IP, port=AIRSIM_PORT, timeout_value=60)
    client.confirmConnection()
    setup_filters(client, patterns)
    log("Logging map points → %s (every %.2fs)" % (os.path.abspath(args.csv), args.interval))

    path = os.path.abspath(args.csv)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    new_file = not os.path.isfile(path)
    csv_file = open(path, "a", newline="", encoding="utf-8")
    w = csv.writer(csv_file)
    if new_file:
        w.writerow(
            [
                "unix_time",
                "name",
                "geo_lat",
                "geo_lon",
                "geo_alt",
                "rel_x",
                "rel_y",
                "rel_z",
                "est_world_x",
                "est_world_y",
                "est_world_z",
                "veh_x",
                "veh_y",
                "veh_z",
                "cam_x",
                "cam_y",
                "cam_z",
            ]
        )

    import cv2

    cv2.namedWindow("HW_5 map logger (preview)", cv2.WINDOW_NORMAL)
    last_t = 0.0
    patterns_ref = patterns

    try:
        while True:
            raw = client.simGetImage(CAMERA_NAME, IMG_SCENE)
            detections = client.simGetDetections(CAMERA_NAME, IMG_SCENE) or []
            frame = None
            if raw:
                frame = cv2.imdecode(airsim.string_to_uint8_array(raw), cv2.IMREAD_COLOR)
            if frame is None:
                frame = np.zeros((240, 320, 3), dtype=np.uint8)

            for det in detections:
                x0 = int(det.box2D.min.x_val)
                y0 = int(det.box2D.min.y_val)
                x1 = int(det.box2D.max.x_val)
                y1 = int(det.box2D.max.y_val)
                cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 255, 0), 1)

            cv2.putText(
                frame,
                "Logging… q=quit",
                (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("HW_5 map logger (preview)", frame)

            now = time.time()
            if now - last_t >= args.interval:
                last_t = now
                state = client.getMultirotorState()
                vp = state.kinematics_estimated.position
                cam_pose = client.simGetCameraInfo(CAMERA_NAME).pose
                cam_t = np.array(
                    [cam_pose.position.x_val, cam_pose.position.y_val, cam_pose.position.z_val],
                    dtype=np.float64,
                )
                for det in detections:
                    gp = det.geo_point
                    rp = det.relative_pose.position
                    try:
                        world, _tcheck, _R = est_world_from_detection(cam_pose, det)
                        ex, ey, ez = float(world[0]), float(world[1]), float(world[2])
                    except Exception:
                        ex = ey = ez = float("nan")
                    w.writerow(
                        [
                            "%.6f" % now,
                            str(det.name),
                            gp.latitude,
                            gp.longitude,
                            gp.altitude,
                            rp.x_val,
                            rp.y_val,
                            rp.z_val,
                            ex,
                            ey,
                            ez,
                            vp.x_val,
                            vp.y_val,
                            vp.z_val,
                            float(cam_t[0]),
                            float(cam_t[1]),
                            float(cam_t[2]),
                        ]
                    )
                csv_file.flush()
                log("Sampled %d detection(s)" % len(detections))

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                client.simClearDetectionMeshNames(CAMERA_NAME, IMG_SCENE)
            if key == ord("a"):
                setup_filters(client, patterns_ref)
    finally:
        csv_file.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
