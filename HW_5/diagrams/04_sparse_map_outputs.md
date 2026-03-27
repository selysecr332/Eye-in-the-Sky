# HW_5 advanced — outputs for “3D map of the area”

```mermaid
flowchart TB
  logs["CSV or NPZ\n(timestamp, pose, det name, xyz)"]
  viz2d["Top-down scatter\nmatplotlib"]
  viz3d["3D scatter or mesh\nmatplotlib / Open3D optional"]
  ply["Export PLY point cloud\nfor Blender or CloudCompare"]

  logs --> viz2d
  logs --> viz3d
  logs --> ply
```

Caption: Start with **sparse labeled points** (houses, cars, trees). Dense reconstruction (full mesh) is a stretch goal — document scope honestly in the report.
