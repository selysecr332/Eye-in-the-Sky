# HW_4 advanced — multi-modal sensing (RGB + infrared + optional depth)

```mermaid
flowchart LR
  cam["Drone camera 0"]
  scene["Scene RGB\n(ImageType.Scene)"]
  ir["Infrared\n(ImageType.Infrared)"]
  dep["Depth optional\n(ImageType.DepthPlanar)"]
  fuse["OpenCV display\nside-by-side or blend"]
  user["Operator / grader"]

  cam --> scene
  cam --> ir
  cam --> dep
  scene --> fuse
  ir --> fuse
  dep --> fuse
  fuse --> user
```

Caption: AirSim can return **several image types per frame**. Infrared is useful for **contrast in foliage / low light** in Unreal; depth helps **ground intersection** for later mapping (HW_5).
