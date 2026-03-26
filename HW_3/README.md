# HW_3 — GitHub, Overleaf, and report workflow

## Purpose

Establish **professional collaboration artifacts**: public or private **GitHub** repository structure, **LaTeX** source on **Overleaf** (or local), and traceability from **commit → figure → section**.

## Deliverable in this folder

- `[HW3] Github_Overleaf_Report.pdf` (or current filename from your course)

## Repository layout (what graders like to see)

```
Drons/
  ALL_HW/           ← this submission pack (README per HW)
  AirSim/           ← upstream + your PythonClient changes
  README.md          ← how to reproduce baseline
  RUN_DRONE_FIND_THINGS.md
  docs/              ← screenshots, diagrams
```

## Code ↔ report traceability (TODO — student)

| Report section | Repo pointer |
|----------------|--------------|
| Methods / Simulator | `README.md` § Simulation Pipeline |
| Vision baseline | `AirSim/PythonClient/detection/find_things_cv.py` |
| Extended work | `ALL_HW/HW_5/README.md` |

## Diagram

| File | Description |
|------|-------------|
| [diagrams/01_git_overleaf_workflow.md](diagrams/01_git_overleaf_workflow.md) | Edit loop: IDE → git → GitHub; Overleaf ↔ PDF |

## Overleaf tips

- Single **main `.tex`**, **`bib`** for references, **figures/** for high-DPI PNG/PDF.
- Use **`\includegraphics`** for detection screenshots from `docs/` or `ALL_HW/HW_4/images/`.
- Add **`hyperref`** for clickable GitHub links in PDF.

## Checklist

- [x] PDF in folder
- [ ] GitHub URL in this README (if allowed): `TODO`
- [ ] Overleaf link (view-only) if allowed: `TODO`
- [ ] Branch/tag for “HW_3 submission”: `TODO`
