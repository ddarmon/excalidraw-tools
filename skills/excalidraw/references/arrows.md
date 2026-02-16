# Arrow Routing Reference

## Edge Calculation

| Edge   | x formula              | y formula               |
|--------|------------------------|-------------------------|
| Top    | `shape.x + width/2`   | `shape.y`                |
| Bottom | `shape.x + width/2`   | `shape.y + height`       |
| Left   | `shape.x`             | `shape.y + height/2`     |
| Right  | `shape.x + width`     | `shape.y + height/2`     |

Arrow `x, y` = the source edge point.
Arrow `points` = offsets from that start position.

## Routing Patterns

| Pattern      | Points                                        | Use Case                  |
|--------------|-----------------------------------------------|---------------------------|
| Down         | `[[0,0], [0,h]]`                              | Vertical connection       |
| Right        | `[[0,0], [w,0]]`                              | Horizontal connection     |
| L-down-right | `[[0,0], [0,h], [w,h]]`                       | Go down, then right       |
| L-right-down | `[[0,0], [w,0], [w,h]]`                       | Go right, then down       |
| L-down-left  | `[[0,0], [0,h], [-w,h]]`                      | Go down, then left        |
| L-left-down  | `[[0,0], [-w,0], [-w,h]]`                     | Go left, then down        |
| U-turn right | `[[0,0], [c,0], [c,dy], [dx,dy]]`             | Loop back (clearance c)   |
| S-shape      | `[[0,0], [0,h1], [w,h1], [w,h2]]`             | Navigate around obstacles |

## Worked Examples

### Straight Down (bottom to top)

```
Source: x=300, y=100, w=200, h=70  → bottom edge: (400, 170)
Target: x=300, y=270, w=200, h=70  → top edge: (400, 270)

Arrow: x=400, y=170, points=[[0,0], [0,100]]
```

### L-Shape (right side to top)

```
Source: x=300, y=300, w=200, h=70  → right edge: (500, 335)
Target: x=600, y=100, w=200, h=70  → top edge: (700, 100)

dx = 700 - 500 = 200
dy = 100 - 335 = -235

Arrow: x=500, y=335, points=[[0,0], [200,0], [200,-235]]
```

### U-Turn (loop back)

```
Source right edge: (500, 335)
Target right edge: (500, 170)

Arrow: x=500, y=335, points=[[0,0], [50,0], [50,-165], [0,-165]]
(50px clearance to the right)
```

## Width/Height Calculation

Arrow `width` and `height` = bounding box of all points:

```
width  = max(abs(p[0]) for p in points)
height = max(abs(p[1]) for p in points)
```

## Staggering Multiple Arrows

When N arrows leave the same edge, spread them evenly:

```
For N arrows from bottom edge:
  positions = [shape.x + shape.width * (0.2 + 0.6*i/(N-1)) for i in range(N)]

2 arrows: 20%, 80% across width
3 arrows: 20%, 50%, 80%
5 arrows: 20%, 35%, 50%, 65%, 80%
```

## Elbow vs Curved Arrows

| Style  | roughness | roundness      | elbowed |
|--------|-----------|----------------|---------|
| Curved | 1         | `{"type": 2}`  | false   |
| Elbow  | 0         | null           | true    |

Use curved for hand-drawn style, elbow for technical diagrams.

## Bidirectional Arrows

```json
{"startArrowhead": "arrow", "endArrowhead": "arrow"}
```

## Arrow Labels

Position standalone text near arrow midpoint:

```json
{
  "type": "text",
  "x": 305, "y": 245,
  "text": "HTTP",
  "fontSize": 14,
  "containerId": null
}
```
