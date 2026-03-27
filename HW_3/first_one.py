"""
HW_3 simple detector starter.

Goal:
- Connect to AirSim while drone is flying in Unreal.
- Read camera frames.
- Get object detections from AirSim filters.
- Draw bounding boxes + names.
- Show count of seen objects on screen.

Run (recommended from repo root with venv310):
  cd c:\\Users\\Selysecr\\Desktop\\Drons
  .\AirSim\PythonClient\detection\venv310\Scripts\python.exe ALL_HW\HW_3\first_one.py
"""

import os
import sys
import cv2


# Make local AirSim Python package importable without installing globally.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYCLIENT = os.path.join(ROOT, "AirSim", "PythonClient")
if PYCLIENT not in sys.path:
    sys.path.insert(0, PYCLIENT)

import airsim  # noqa: E402


AIRSIM_IP = "127.0.0.1"
AIRSIM_PORT = 41451
CAMERA_NAME = "0"
IMAGE_TYPE = airsim.ImageType.Scene
DETECTION_RADIUS_CM = 200 * 100
WINDOW_NAME = "HW_3 first_one.py - detections"

# Defaults tuned for AirSim NH-style suburban maps (names from World Outliner).
# Your logs showed: Car_*, Tree_*, Bench_*, Birch_*, House-style actors (e.g. Small House_*).
# Optional override without editing this file (PowerShell):
#   $env:AIRSIM_DETECT_FILTERS="Car*,Birch*,Bench*"
DEFAULT_OBJECTS_TO_FIND = [
    "Car*",
    "House*",
    "Small*",   # e.g. Small House_3
    "Tree*",
    "Bench*",
    "Birch*",   # Birch_01_160, Birch_10, ...
]


def objects_to_find():
    env = os.environ.get("AIRSIM_DETECT_FILTERS", "").strip()
    if not env:
        return list(DEFAULT_OBJECTS_TO_FIND)
    parts = [p.strip() for p in env.split(",") if p.strip()]
    return parts if parts else list(DEFAULT_OBJECTS_TO_FIND)


def log(msg):
    print(msg, flush=True)


def connect_client():
    log("Connecting to AirSim at %s:%d ..." % (AIRSIM_IP, AIRSIM_PORT))
    client = airsim.MultirotorClient(ip=AIRSIM_IP, port=AIRSIM_PORT, timeout_value=60)
    client.confirmConnection()
    log("Connected to AirSim.")
    return client


def setup_filters(client, patterns):
    # Clear old filters from earlier runs, then add only current list.
    client.simClearDetectionMeshNames(CAMERA_NAME, IMAGE_TYPE)
    client.simSetDetectionFilterRadius(CAMERA_NAME, IMAGE_TYPE, DETECTION_RADIUS_CM)
    for pattern in patterns:
        client.simAddDetectionFilterMeshName(CAMERA_NAME, IMAGE_TYPE, pattern)
    log("Filters set: %s" % patterns)


def main():
    patterns = objects_to_find()
    if os.environ.get("AIRSIM_DETECT_FILTERS", "").strip():
        log("Using AIRSIM_DETECT_FILTERS from environment.")
    else:
        log("Using DEFAULT_OBJECTS_TO_FIND (set AIRSIM_DETECT_FILTERS to override).")
    client = connect_client()
    setup_filters(client, patterns)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    last_count = -1

    log("Press q=quit, c=clear filters, a=add filters")

    while True:
        raw = client.simGetImage(CAMERA_NAME, IMAGE_TYPE)
        if not raw:
            continue

        frame = cv2.imdecode(airsim.string_to_uint8_array(raw), cv2.IMREAD_COLOR)
        if frame is None:
            continue

        detections = client.simGetDetections(CAMERA_NAME, IMAGE_TYPE) or []
        count = len(detections)

        for det in detections:
            x0 = int(det.box2D.min.x_val)
            y0 = int(det.box2D.min.y_val)
            x1 = int(det.box2D.max.x_val)
            y1 = int(det.box2D.max.y_val)
            name = str(det.name)

            cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 255, 0), 2)
            cv2.putText(
                frame,
                name,
                (x0, max(15, y0 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        # Draw object count on top-left.
        cv2.putText(
            frame,
            "Seen objects: %d" % count,
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        if count != last_count:
            last_count = count
            unique_names = sorted({str(d.name) for d in detections})
            sample = ", ".join(unique_names[:8])
            suffix = " ..." if len(unique_names) > 8 else ""
            log("Seen objects: %d" % count)
            if unique_names:
                log("Name sample (%d): %s%s" % (len(unique_names), sample, suffix))

        cv2.imshow(WINDOW_NAME, frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("c"):
            client.simClearDetectionMeshNames(CAMERA_NAME, IMAGE_TYPE)
            log("Filters cleared")
        if key == ord("a"):
            for pattern in patterns:
                client.simAddDetectionFilterMeshName(CAMERA_NAME, IMAGE_TYPE, pattern)
            log("Filters re-added: %s" % patterns)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
