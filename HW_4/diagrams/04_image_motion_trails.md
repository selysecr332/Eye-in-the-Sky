# HW_4 advanced — motion diagram in image space (2D trails)

```mermaid
flowchart TD
  det["simGetDetections each frame"]
  cen["Box centroid u,v per object"]
  idn["Match boxes frame-to-frame\n(IoU or nearest centroid)"]
  trail["Keep last K positions\nper track id"]
  draw["Draw polyline / fading trail\non RGB or IR overlay"]

  det --> cen --> idn --> trail --> draw
```

Caption: A **motion diagram** in the camera view: each tracked object leaves a short **2D path** so reviewers see movement relative to the lens (not yet a world map).
