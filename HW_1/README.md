# HW_1 — From idea to plan: research topic, toolchain, and environment

## 1. Idea (from the beginning)

**Goal:** Study a **software- and simulation-based** pipeline where a **multirotor** is controlled in a **high-fidelity 3D simulator** (Unreal + **AirSim**) with **PX4** autopilot software, while a **Python** client consumes **camera** data for **perception** (object detection / future ML).

**Why simulation first:** Repeatable experiments, no hardware risk, full access to ground-truth poses and labeled scene objects (via Unreal actor names and AirSim APIs).

**Local PDF in this folder:**  
`[HW1] Research Topic and Conference Selection.pdf` — formal write-up of topic and target venue.

---

## 2. What had to be installed / programs used

| Component | Purpose |
|-----------|---------|
| **Windows 10/11** | Host OS for Unreal, Python, QGC |
| **Unreal Engine** (+ project e.g. AirSim NH / Blocks) | Visual world + AirSim plugin |
| **AirSim** (Unreal plugin + `PythonClient`) | RPC API: images, detections, vehicle state |
| **PX4-Autopilot** (often **WSL** / Linux) | Autopilot SITL |
| **QGroundControl** | Mission planning, telemetry |
| **Python 3.10** (venv `venv310`) | `airsim`, `opencv-python`, `numpy`, `msgpack-rpc-python` |
| **Git** | Version control |
| **Optional:** **LaTeX / Overleaf** | Report writing (see HW_3) |

Detailed install order and versions: see repo root **`README.md`** and **`RUN_DRONE_FIND_THINGS.md`**.

---

## 3. Code (during this phase)

At HW_1 the emphasis is **planning and environment setup**; production scripts live in the main tree:

| Artifact | Location |
|----------|----------|
| Python detection entry point | `AirSim/PythonClient/detection/find_things_cv.py` |
| Add object types (naming) | `AirSim/PythonClient/detection/ADD_NEW_OBJECT_TYPE.md` |

*(Paste small excerpts into this README only if your course requires inline listings; otherwise link to files in-repo.)*

---

## 4. Diagrams

| File | Description |
|------|-------------|
| [diagrams/01_system_context.md](diagrams/01_system_context.md) | High-level actors: pilot / GCS, PX4, AirSim, Python CV |
| [diagrams/02_dev_environment.md](diagrams/02_dev_environment.md) | Dev machine topology (Windows + optional WSL) |

**TODO (student):** Export PNG/SVG from GitHub’s Mermaid preview or [mermaid.live](https://mermaid.live) into **`images/`** and embed here for a polished PDF.

---

## 5. Plan (what needed to be done next)

1. Verify **PX4 SITL** launches and talks to **QGroundControl** (UDP).
2. Open **Unreal** project → **Play** → confirm **AirSim** connects (RPC port, e.g. **41451**).
3. Create **Python venv**, install clients, run **`find_things_cv.py`** once to validate camera + detection path.
4. Lock **research questions** (e.g. perception for search-and-rescue in suburban scenes) and **target conference / workshop** (see PDF).
5. Freeze **folder structure** for homework hand-ins (`ALL_HW/HW_n`).

---

## 6. Deliverables checklist (HW_1)

- [x] Topic + venue rationale (PDF in folder)
- [x] Written plan: installs, programs, and next steps (this README)
- [ ] Optional: 1–2 figures in **`images/`** (simulator + QGC screenshot)

---

## Images folder

Place exported diagrams and screenshots in **`images/`** and reference them like:

```markdown
![System context](images/01_system_context.png)
```

See **`images/README.txt`** for naming suggestions.
