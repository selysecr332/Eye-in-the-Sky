# Course submissions — Drone simulation & computer vision

This folder collects **five homework milestones** for the project: **simulated drone flight (PX4 + AirSim + QGroundControl)** and **real-time vision** from the onboard camera (AirSim detection API + OpenCV).

Use each **`HW_n/README.md`** as the entry point for that milestone: objectives, deliverables, diagrams, and pointers to code in the main repository.

---

## Folder map

| Folder | Theme | Highlights |
|--------|--------|------------|
| [**HW_1**](HW_1/README.md) | Foundations & research framing | Problem statement, toolchain, install plan, environment diagram |
| [**HW_2**](HW_2/README.md) | Research refinement | Topic updates, conference / venue alignment |
| [**HW_3**](HW_3/README.md) | Collaboration & reporting | GitHub, Overleaf/report workflow |
| [**HW_4**](HW_4/README.md) | Simulation & baseline vision | PX4 + AirSim + QGC + `find_things_cv.py` detection |
| [**HW_5**](HW_5/README.md) | Extensions | Filtering (e.g. red cars), logging CSV, optional nav + ML training |

---

## Repository roots (for code)

From the **Drons** repo root (parent of `ALL_HW`):

| Path | Role |
|------|------|
| `AirSim/PythonClient/detection/` | Detection scripts, venv, `find_things_cv.py`, `train_detector.py` |
| `README.md` | Project overview & reproducibility |
| `RUN_DRONE_FIND_THINGS.md` | Step-by-step run order |
| `docs/` | Screenshots / figures (add yours here and link from HW READMEs) |

---

For instructors: see **[SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md)**.

---

## Suggested assets before upload

- [ ] Add **screenshots** under each `HW_n/images/` (or central `docs/`) and link them in the corresponding README.
- [ ] Replace placeholder text marked **TODO (student)** with your name, course number, and dates.
- [ ] Confirm PDFs in `HW_*` are allowed to be public on GitHub (copyright).

---

## Author

**TODO (student):** Your name — Course — Term — Institution
