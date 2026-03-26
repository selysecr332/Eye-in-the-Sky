# HW_4 — Simulation integration & baseline computer vision

## Objective

Demonstrate an **end-to-end loop**:

1. **PX4 SITL** + **Unreal/AirSim** (environment running in **Play** mode).
2. **QGroundControl** (optional) for missions / telemetry.
3. **Python** client: live **front camera** stream + **AirSim detection API** (`simGetDetections`) with **OpenCV** visualization.

## Primary code artifacts

| File | Role |
|------|------|
| [`../../AirSim/PythonClient/detection/find_things_cv.py`](../../AirSim/PythonClient/detection/find_things_cv.py) | Connects to AirSim, draws bounding boxes and labels |
| [`../../AirSim/PythonClient/detection/ADD_NEW_OBJECT_TYPE.md`](../../AirSim/PythonClient/detection/ADD_NEW_OBJECT_TYPE.md) | How Unreal names map to `OBJECTS_TO_FIND` wildcards |
| [`../../RUN_DRONE_FIND_THINGS.md`](../../RUN_DRONE_FIND_THINGS.md) | Run order (PX4 → Unreal → QGC → script) |

## How to run (short)

```powershell
cd ..\..\AirSim\PythonClient\detection
.\venv310\Scripts\python.exe find_things_cv.py
```

Configure **`OBJECTS_TO_FIND`** (e.g. `Car*`, `House*`) to match **World Outliner** names in your level.

## Concepts for the report

- **Detection is name-based:** AirSim filters by **actor / mesh name patterns**, not color.
- **Camera:** default front camera id `"0"`; image type **Scene**.
- **Port:** RPC to localhost (example **41451**; confirm in your `settings.json` if customized).

## Diagrams

| File | Description |
|------|-------------|
| [diagrams/01_data_flow_hw4.md](diagrams/01_data_flow_hw4.md) | Camera image + detection JSON RPC |
| [diagrams/02_detection_filter_logic.md](diagrams/02_detection_filter_logic.md) | From `OBJECTS_TO_FIND` to on-screen boxes |

## Expected screenshots (`images/`)

**TODO (student):** Add:

- `unreal_play_drone.png` — simulator in Play.
- `opencv_detections.png` — OpenCV window with boxes + labels.
- `terminal_connected.png` — “Connected to AirSim” + detection counts.

## Rubric-friendly checklist

- [ ] Repro steps documented (cite `RUN_DRONE_FIND_THINGS.md` or restate).
- [ ] At least one figure with **captions** explaining what is detected and why names matter.
- [ ] Brief **failure modes** (no Play mode, wrong filters, stale detection filters — script clears on start).

## References

AirSim image & APIs: [AirSim docs — Image APIs](https://microsoft.github.io/AirSim/image_apis/)
