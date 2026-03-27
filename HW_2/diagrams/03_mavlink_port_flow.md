# HW_2 MAVLink port flow (from pxh commands)

```mermaid
flowchart TB
  CMD["pxh commands:\n- mavlink stop-all\n- mavlink start -u 18570 ...\n- mavlink start -u 14580 ...\n- mavlink start -u 14280 ...\n- mavlink start -u 13030 ..."]
  PX4["PX4 SITL MAVLink instances"]
  QGC["QGroundControl link(s)"]
  AS["AirSim / Unreal bridge"]
  DBG["Other telemetry/debug consumers"]

  CMD --> PX4
  PX4 -->|u 14580 (example)| AS
  PX4 -->|u 18570 / other stream| QGC
  PX4 -->|u 14280, u 13030| DBG
```

Notes:
- Exact consumer-to-port mapping depends on your runtime link setup.
- The important principle is to keep **QGC link ports**, **AirSim settings**, and **PX4 mavlink starts** consistent.
