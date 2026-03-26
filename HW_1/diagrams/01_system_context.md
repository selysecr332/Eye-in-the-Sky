# System context (Mermaid)

Render in GitHub, VS Code (Mermaid extension), or https://mermaid.live .

```mermaid
flowchart LR
  subgraph GCS["Ground control"]
    QGC["QGroundControl"]
  end
  subgraph AP["Autopilot (SITL)"]
    PX4["PX4"]
  end
  subgraph SIM["Simulator"]
    UE["Unreal Engine"]
    AS["AirSim plugin"]
  end
  subgraph CV["Perception (host)"]
    PY["Python + OpenCV\nfind_things_cv.py"]
  end
  QGC <-- UDP MAVLink --> PX4
  PX4 <-- lockstep / UDP --> AS
  UE --- AS
  AS <-- RPC :41451 --> PY
```

**Caption for report:** QGroundControl commands PX4; AirSim exchanges physics/autopilot data with PX4; the Python client uses AirSim’s RPC API for images and detections.
