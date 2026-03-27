# HW_3 runtime communication (PX4 - AirSim - Unreal - QGroundControl)

```mermaid
flowchart LR
  subgraph WSL["WSL2 Linux"]
    px4["PX4 SITL"]
  end

  subgraph WIN["Windows"]
    qgc["QGroundControl"]
    unreal["Unreal Engine"]
    airsim["AirSim plugin"]
    py["first_one.py"]
    json["Documents/AirSim/settings.json"]
  end

  json --> airsim
  unreal --- airsim
  px4 <-->|MAVLink UDP/TCP| airsim
  px4 <-->|MAVLink telemetry| qgc
  py <-->|RPC 41451| airsim
```

Caption: `first_one.py` reads images + detections through AirSim RPC, while PX4 and QGroundControl communicate through MAVLink.
