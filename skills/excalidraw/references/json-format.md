# Excalidraw JSON Format Reference

## File Structure

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [],
  "appState": {
    "gridSize": 20,
    "gridStep": 5,
    "gridModeEnabled": false,
    "viewBackgroundColor": "#ffffff"
  },
  "files": {}
}
```

## Required Element Properties

Every element MUST have all of these:

```json
{
  "id": "unique-string",
  "type": "rectangle",
  "x": 100,
  "y": 100,
  "width": 200,
  "height": 80,
  "angle": 0,
  "strokeColor": "#1e1e1e",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "groupIds": [],
  "frameId": null,
  "index": "a0",
  "roundness": null,
  "seed": 12345,
  "version": 1,
  "versionNonce": 67890,
  "isDeleted": false,
  "boundElements": [],
  "updated": 1700000000000,
  "link": null,
  "locked": false
}
```

## Roundness by Type

| Type        | roundness value        |
|-------------|------------------------|
| rectangle   | `{"type": 3}`          |
| ellipse     | `{"type": 2}`          |
| diamond     | `{"type": 2}`          |
| arrow       | `{"type": 2}` or null  |
| text        | `null`                 |
| line        | `{"type": 2}`          |

## Text Elements

Additional required properties for text:

```json
{
  "text": "Label Text",
  "fontSize": 20,
  "fontFamily": 1,
  "textAlign": "center",
  "verticalAlign": "middle",
  "containerId": "parent-shape-id-or-null",
  "originalText": "Label Text",
  "autoResize": true
}
```

- `fontFamily`: 1 = Virgil (hand-drawn), 2 = Helvetica, 3 = Cascadia (mono)
- `containerId`: set to shape ID for bound labels, `null` for standalone
- Bound text: `verticalAlign: "middle"`, standalone: `verticalAlign: "top"`

## Arrow Elements

Additional required properties for arrows:

```json
{
  "points": [[0, 0], [0, 100]],
  "startBinding": {
    "elementId": "source-shape-id",
    "focus": 0,
    "gap": 1,
    "fixedPoint": null
  },
  "endBinding": {
    "elementId": "target-shape-id",
    "focus": 0,
    "gap": 1,
    "fixedPoint": null
  },
  "startArrowhead": null,
  "endArrowhead": "arrow",
  "elbowed": false
}
```

- `points`: array of [x, y] offsets relative to the arrow's x, y position
- `startArrowhead` / `endArrowhead`: `null`, `"arrow"`, `"bar"`, `"dot"`, `"triangle"`
- Set bindings to `null` for unconnected arrows
- `elbowed: true` + `roundness: null` + `roughness: 0` for right-angle routing

## fixedPoint Values for Bindings

| Edge          | fixedPoint  |
|---------------|-------------|
| Top center    | `[0.5, 0]`  |
| Bottom center | `[0.5, 1]`  |
| Left center   | `[0, 0.5]`  |
| Right center  | `[1, 0.5]`  |

## Index Property

The `index` field uses fractional indexing for z-ordering:
`"a0"`, `"a1"`, ... `"a9"`, `"aA"`, `"aB"`, ... `"aZ"`, `"aa"`, `"ab"`, ...

Elements with later indices render on top.

## Grouping with Dashed Rectangles

For visual grouping (namespaces, containers):

```json
{
  "type": "rectangle",
  "strokeStyle": "dashed",
  "backgroundColor": "transparent",
  "roughness": 0,
  "roundness": null,
  "boundElements": null
}
```

Add a standalone text label (no containerId) near the top-left corner.

## Freedraw Elements

Freehand drawings have a `points` array of [x, y] offsets and:

```json
{
  "type": "freedraw",
  "points": [[0, 0], [1.5, 2.3], ...],
  "pressures": [],
  "simulatePressure": true
}
```

These are created by the user drawing in Excalidraw, not generated programmatically.
