#!/usr/bin/env python3
"""
Export WatchfulEye theme tokens from `frontend/src/index.css` into Tokens Studio–friendly JSON.

Outputs:
  - figma/tokens.light.json
  - figma/tokens.dark.json

Notes:
  - Color values are converted from HSL (space-separated CSS variables) to hex.
  - Non-color variables (e.g. --radius) are exported as dimension tokens.
"""

from __future__ import annotations

import colorsys
import json
import re
from pathlib import Path
from typing import Dict, Tuple


ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "frontend" / "src" / "index.css"
OUT_LIGHT = ROOT / "figma" / "tokens.light.json"
OUT_DARK = ROOT / "figma" / "tokens.dark.json"


VAR_RE = re.compile(r"^\s*--(?P<name>[a-z0-9\-]+)\s*:\s*(?P<value>[^;]+)\s*;\s*$", re.I)
HSL_TRIPLE_RE = re.compile(
    r"^(?P<h>-?\d+(?:\.\d+)?)\s+(?P<s>\d+(?:\.\d+)?)%\s+(?P<l>\d+(?:\.\d+)?)%$"
)


def hsl_to_hex(h: float, s: float, l: float) -> str:
  # colorsys uses HLS (not HSL): (h, l, s) in 0..1
  r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
  return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def extract_vars(css_text: str) -> Tuple[Dict[str, str], Dict[str, str]]:
  mode = None  # None | "light" | "dark"
  light: Dict[str, str] = {}
  dark: Dict[str, str] = {}

  for raw in css_text.splitlines():
    line = raw.strip()
    if line.startswith(":root") and line.endswith("{"):
      mode = "light"
      continue
    if line.startswith(".dark") and line.endswith("{"):
      mode = "dark"
      continue
    if mode and line == "}":
      mode = None
      continue

    if not mode:
      continue

    m = VAR_RE.match(raw)
    if not m:
      continue

    name = m.group("name").strip()
    value = m.group("value").strip()
    if mode == "light":
      light[name] = value
    else:
      dark[name] = value

  return light, dark


def to_tokens(var_map: Dict[str, str]) -> Dict[str, object]:
  colors: Dict[str, object] = {}
  dimensions: Dict[str, object] = {}

  for name, value in sorted(var_map.items()):
    hsl = HSL_TRIPLE_RE.match(value)
    if hsl:
      h = float(hsl.group("h"))
      s = float(hsl.group("s"))
      l = float(hsl.group("l"))
      colors[name] = {"value": hsl_to_hex(h, s, l), "type": "color"}
      continue

    # Fallback: export as dimension-like token
    dimensions[name] = {"value": value, "type": "dimension"}

  out: Dict[str, object] = {}
  if colors:
    out["color"] = colors
  if dimensions:
    out["dimension"] = dimensions
  return out


def main() -> int:
  css_text = CSS_PATH.read_text(encoding="utf-8")
  light_vars, dark_vars = extract_vars(css_text)

  OUT_LIGHT.write_text(json.dumps(to_tokens(light_vars), indent=2) + "\n", encoding="utf-8")
  OUT_DARK.write_text(json.dumps(to_tokens(dark_vars), indent=2) + "\n", encoding="utf-8")

  print(f"Wrote: {OUT_LIGHT}")
  print(f"Wrote: {OUT_DARK}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())


