# HW_5 advanced — placing objects in world space (for 3D maps)

```mermaid
flowchart LR
  det["DetectionInfo\nname, box2D, relative_pose"]
  state["Vehicle pose\ngetMultirotorState"]
  xform["Transform camera or body frame\nto world NED"]
  pt["World point\ne.g. x,y,z or lat,lon,alt"]
  store["Append to trajectory + object map"]

  det --> xform
  state --> xform
  xform --> pt --> store
```

Caption: AirSim gives **relative_pose** per detection; combined with **drone pose**, you can estimate a **3D location** per object over time and accumulate a **sparse map**.
