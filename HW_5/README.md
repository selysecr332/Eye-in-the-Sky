# HW_5 — Extensions: filtering, logging, navigation hook, ML path

## Objective

Go beyond name-only detection:

1. **Semantic filtering in pixels** (example: **red** vehicles when all cars share the `Car_*` name — HSV ROI check).
2. **Structured logging** (CSV: time, pose, boxes, flags).
3. **Optional navigation** (yaw toward largest detection — AirSim API; conflicts possible with manual/QGC control).
4. **Optional ML** (same feature vector for `train_detector.py` + sklearn model; **requires `scikit-learn` install**).

## Code map

| File | Role |
|------|------|
| [`../../AirSim/PythonClient/detection/find_things_cv.py`](../../AirSim/PythonClient/detection/find_things_cv.py) | Main script: filters, CSV, nav toggle, optional ML gate |
| [`../../AirSim/PythonClient/detection/detection_features.py`](../../AirSim/PythonClient/detection/detection_features.py) | 17-D feature vector (shared with trainer) |
| [`../../AirSim/PythonClient/detection/train_detector.py`](../../AirSim/PythonClient/detection/train_detector.py) | Train `.pkl` from `positive/` and `negative/` crop folders |

## Configuration knobs (teacher-friendly “methods” section)

- `OBJECTS_TO_FIND` — AirSim name wildcards.
- `FILTER_RED_CARS_ONLY` — HSV red fraction gate on `Car*` boxes.
- `LOG_ENABLE`, `LOG_DIR`, `LOG_EVERY_SEC` — CSV traces.
- `NAV_TRACK`, `NAV_YAW_GAIN_DEG` — press **`t`** in OpenCV to toggle.
- `ML_MODEL_PATH`, `ML_GATE_PREFIX`, `ML_THRESHOLD` — sklearn gate (optional).

## Diagrams

| File | Description |
|------|-------------|
| [diagrams/01_pipeline_hw5.md](diagrams/01_pipeline_hw5.md) | Extended pipeline |
| [diagrams/02_ml_optional_path.md](diagrams/02_ml_optional_path.md) | Crops → train → `.pkl` → runtime |

## ML training (if network allows `pip install scikit-learn`)

```powershell
cd ..\..\AirSim\PythonClient\detection
.\venv310\Scripts\python.exe train_detector.py --positive crops\positive --negative crops\negative --out red_car_clf.pkl
```

If install fails, document the **network error** and rely on **HSV-only** filtering in the report (honest limitation).

## Deliverables checklist

- [ ] Explain **why** name-only detection is insufficient for “red car” (same `Car_*` label).
- [ ] Screenshot of **CSV** sample or describe columns (privacy: no secrets).
- [ ] One figure for **optional** nav or ML path.
- [ ] **Ethics / safety** one-liner: simulation-only; API control vs. pilot authority.

## Suggested `images/`

- `opencv_red_filter.png` — only red cars boxed (or best effort).
- `detection_logs_csv_snippet.png` — blurred path if needed.
- `optional_nav_track_overlay.png` — “NAV TRACK” text on frame.
