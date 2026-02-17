#!/usr/bin/env bash
set -euo pipefail

INPUT="diagrams"
RENDERER_URL="${RENDERER_URL:-http://localhost:3004}"
WIDTH="${WIDTH:-}"
HEIGHT="${HEIGHT:-}"
DPI="${DPI:-}"
ZOOM="${ZOOM:-}"
SCALE="${SCALE:-}"
DEFAULT_WIDTH="${DEFAULT_WIDTH:-1600}"
BACKGROUND="${BACKGROUND:-}"
TRANSPARENT="${TRANSPARENT:-false}"
HAS_SIZE_OVERRIDE=0

usage() {
  cat <<'EOF'
Usage:
  scripts/render_diagrams.sh [options]

Options:
  --input PATH          File or directory to render (default: diagrams)
  --renderer-url URL    Renderer base URL (default: http://localhost:3004)
  --width PX            Output width in pixels
  --height PX           Output height in pixels
  --dpi N               Output DPI (used with zoom mode)
  --zoom N              Zoom factor before DPI scaling (used with zoom mode)
  --scale N             Pixel scale factor (e.g. 2 for 2x resolution)
  --background COLOR    Background color (e.g. #ffffff, white)
  --transparent BOOL    Transparent background: true/false (default: false)
  -h, --help            Show this help

Behavior:
  - If input is a directory, renders all *.excalidraw recursively.
  - Outputs are written next to each source file as <name>.png.
  - Default size mode is display-oriented width rendering at 1600px.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)
      INPUT="$2"
      shift 2
      ;;
    --renderer-url)
      RENDERER_URL="$2"
      shift 2
      ;;
    --dpi)
      DPI="$2"
      HAS_SIZE_OVERRIDE=1
      shift 2
      ;;
    --zoom)
      ZOOM="$2"
      HAS_SIZE_OVERRIDE=1
      shift 2
      ;;
    --width)
      WIDTH="$2"
      HAS_SIZE_OVERRIDE=1
      shift 2
      ;;
    --height)
      HEIGHT="$2"
      HAS_SIZE_OVERRIDE=1
      shift 2
      ;;
    --scale)
      SCALE="$2"
      shift 2
      ;;
    --background)
      BACKGROUND="$2"
      shift 2
      ;;
    --transparent)
      TRANSPARENT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -e "$INPUT" ]]; then
  echo "Input path does not exist: $INPUT" >&2
  exit 1
fi

declare -a FILES=()
if [[ -d "$INPUT" ]]; then
  while IFS= read -r file; do
    FILES+=("$file")
  done < <(find "$INPUT" -type f -name "*.excalidraw" | sort)
else
  if [[ "$INPUT" != *.excalidraw ]]; then
    echo "Input file must end with .excalidraw: $INPUT" >&2
    exit 1
  fi
  FILES+=("$INPUT")
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No .excalidraw files found under: $INPUT" >&2
  exit 1
fi

BASE_URL="${RENDERER_URL%/}/render/png"
QUERY="?transparent=${TRANSPARENT}"

if [[ $HAS_SIZE_OVERRIDE -eq 0 ]]; then
  QUERY="${QUERY}&width=${DEFAULT_WIDTH}"
fi

if [[ -n "$WIDTH" ]]; then
  QUERY="${QUERY}&width=${WIDTH}"
fi
if [[ -n "$HEIGHT" ]]; then
  QUERY="${QUERY}&height=${HEIGHT}"
fi
if [[ -n "$DPI" ]]; then
  QUERY="${QUERY}&dpi=${DPI}"
fi
if [[ -n "$ZOOM" ]]; then
  QUERY="${QUERY}&zoom=${ZOOM}"
fi
if [[ -n "$SCALE" ]]; then
  QUERY="${QUERY}&scale=${SCALE}"
fi

if [[ -n "$BACKGROUND" ]]; then
  BG_ENCODED="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$BACKGROUND")"
  QUERY="${QUERY}&background=${BG_ENCODED}"
fi

for file in "${FILES[@]}"; do
  out="${file%.excalidraw}.png"
  tmp="${out}.tmp.$$"
  echo "Rendering ${file} -> ${out}"
  curl -fsS -X POST \
    "${BASE_URL}${QUERY}" \
    -H "Content-Type: text/plain" \
    --data-binary "@${file}" \
    -o "$tmp"
  mv "$tmp" "$out"
done

echo "Rendered ${#FILES[@]} file(s)."
