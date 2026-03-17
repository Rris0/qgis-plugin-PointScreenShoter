# PointScreenShoter (QGIS Plugin)

PointScreenShoter exports **one map screenshot per point feature** at a fixed scale (e.g. **1:200**) using the **currently visible layers** and **QGIS symbology**.

Each output image is centered on the point and saved as **JPG/PNG** together with a matching **world file** (e.g. `*.jgw` / `*.pgw`) so the screenshot is **georeferenced**.

## Key features

- Export **georeferenced** screenshots (image + world file)
- Uses **all visible map layers** from the current QGIS map (rasters, WMS/WMTS/XYZ, vectors, etc.)
- Point-centered extent at an exact **target scale**
- File naming by selected **attribute field** (with safe filename cleanup) or by **FID**
- Optional **Info Panel overlay** ("place-name style"):
  - North arrow (respects map rotation)
  - Scale bar (matches the image scale)
  - Point ID / name
  - XYZ table (from geometry or selected attribute fields)
- Export all points or **only selected** points

## Installation

1. Download the ZIP release.
2. In QGIS go to **Plugins → Manage and Install Plugins… → Install from ZIP**.
3. Select the downloaded ZIP.

## Usage

1. Open your QGIS project and make sure the layers you want on the screenshot are **visible**.
2. Open **PointScreenShoter**.
3. Choose:
   - Point layer
   - Naming field (optional)
   - Scale (denominator, e.g. `200` for 1:200)
   - Output folder
   - Image size and format
4. (Optional) Enable **Info Panel overlay** and select XYZ fields if needed.
5. Click **Export**.

## Notes

- The exported image is georeferenced in the **project/map CRS**.
- If you use online layers (WMS/XYZ), export speed depends on network and cache.

## Author

Richard Reichel (risoreichel@gmail.com)
