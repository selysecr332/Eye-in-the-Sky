# HW_2 MAVLink port flow (from pxh commands)

```mermaid
flowchart TB
  cmd["pxh commands<br/>mavlink stop-all<br/>mavlink start -u 18570<br/>mavlink start -u 14580<br/>mavlink start -u 14280<br/>mavlink start -u 13030"]
  px4_node["PX4 SITL mavlink instances"]
  qgc_node["QGroundControl link"]
  airsim_node["AirSim Unreal bridge"]
  debug_node["Other telemetry consumers"]
  port_a["Port 14580"]
  port_b["Port 18570"]
  port_c["Ports 14280 and 13030"]

  cmd --> px4_node
  px4_node --> port_a --> airsim_node
  px4_node --> port_b --> qgc_node
  px4_node --> port_c --> debug_node
```

Notes:
- Exact consumer-to-port mapping depends on your runtime link setup.
- The important principle is to keep **QGC link ports**, **AirSim settings**, and **PX4 mavlink starts** consistent.
