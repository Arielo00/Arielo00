#!/usr/bin/env python3
"""Select a thought and render matching dark/light SVG cards.

The selection is deterministic for a UTC calendar date, so rerunning the
workflow on the same day never creates a noisy second commit.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import textwrap
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "thoughts.json"
ASSET_DIR = ROOT / "assets"

THEMES = {
    "dark": {
        "background": "#080b11",
        "panel": "#0d131b",
        "border": "#273441",
        "grid": "#91a4b8",
        "accent": "#70d2c6",
        "secondary": "#c9a96a",
        "text": "#e7edf2",
        "muted": "#788695",
        "glow": "#70d2c6",
    },
    "light": {
        "background": "#e4ded0",
        "panel": "#f6f2e8",
        "border": "#bbb3a5",
        "grid": "#172c35",
        "accent": "#147c78",
        "secondary": "#9a6d2f",
        "text": "#172c35",
        "muted": "#697477",
        "glow": "#147c78",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="UTC date used for selection (YYYY-MM-DD); defaults to today.",
    )
    parser.add_argument(
        "--index",
        type=int,
        help="Render a specific zero-based entry instead of date selection.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate inputs and report whether existing SVGs are current.",
    )
    return parser.parse_args()


def load_thoughts() -> list[dict[str, Any]]:
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {DATA_FILE}: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("thoughts.json must contain a non-empty JSON array")

    required = {"id", "kind", "text", "author", "source", "source_url"}
    seen_ids: set[str] = set()
    for position, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Entry {position} must be an object")
        missing = required - item.keys()
        if missing:
            raise ValueError(f"Entry {position} is missing: {', '.join(sorted(missing))}")
        if item["id"] in seen_ids:
            raise ValueError(f"Duplicate thought id: {item['id']}")
        seen_ids.add(item["id"])
        if item["kind"] not in {"quotation", "original"}:
            raise ValueError(f"Entry {item['id']} has an invalid kind")
        for field in ("id", "text", "author", "source"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise ValueError(f"Entry {item['id']} has an invalid {field}")
        if item["kind"] == "quotation" and not isinstance(item["source_url"], str):
            raise ValueError(f"Quotation {item['id']} requires a source_url")
        if item["kind"] == "original" and item["source_url"] is not None:
            raise ValueError(f"Original {item['id']} must use a null source_url")
    return payload


def select_thought(
    thoughts: list[dict[str, Any]], selection_date: date, index: int | None
) -> tuple[int, dict[str, Any]]:
    selected_index = selection_date.toordinal() % len(thoughts) if index is None else index
    if not 0 <= selected_index < len(thoughts):
        raise ValueError(f"index must be between 0 and {len(thoughts) - 1}")
    return selected_index, thoughts[selected_index]


def quote_lines(text: str) -> list[str]:
    lines = textwrap.wrap(
        text,
        width=62,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if len(lines) > 3:
        lines = textwrap.wrap(
            text,
            width=72,
            break_long_words=False,
            break_on_hyphens=False,
        )
    if len(lines) > 3:
        raise ValueError(f"Thought is too long for the card: {text}")
    return lines


def render_svg(
    thought: dict[str, Any], theme_name: str, selected_index: int, total: int
) -> str:
    theme = THEMES[theme_name]
    lines = quote_lines(thought["text"])
    font_size = 31 if len(thought["text"]) <= 92 else 28
    line_height = font_size + 12
    first_y = 182 - ((len(lines) - 1) * line_height) / 2
    tspans = "\n".join(
        f'        <tspan x="104" y="{first_y + line_no * line_height:.0f}">{html.escape(line)}</tspan>'
        for line_no, line in enumerate(lines)
    )
    source = html.escape(thought["source"])
    author = html.escape(thought["author"])
    label = "VERIFIED QUOTATION" if thought["kind"] == "quotation" else "ORIGINAL FIELD NOTE"
    marker = f"{selected_index + 1:02d} / {total:02d}"
    url = thought["source_url"]
    source_node = (
        f'<a href="{html.escape(url, quote=True)}" target="_blank">'
        f'<text x="104" y="302" class="mono source">SOURCE // {source} ↗</text></a>'
        if url
        else f'<text x="104" y="302" class="mono source">SOURCE // {source}</text>'
    )
    paper_texture = (
        '<path d="M36 83H1164M36 337H1164" stroke="{border}"/>'
        if theme_name == "light"
        else '<rect x="36" y="36" width="1128" height="324" rx="12" fill="url(#grid)"/>'
    ).format(**theme)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="396" viewBox="0 0 1200 396" role="img" aria-labelledby="title desc">
  <title id="title">Current research thought</title>
  <desc id="desc">{html.escape(thought['text'])} — {author}</desc>
  <defs>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M32 0H0V32" fill="none" stroke="{theme['grid']}" stroke-opacity=".045"/>
    </pattern>
    <filter id="glow" x="-200%" y="-200%" width="500%" height="500%">
      <feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <style>
      .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}}
      .serif{{font-family:Georgia,"Times New Roman",serif}}
      .label{{fill:{theme['secondary']};font-size:11px;font-weight:700;letter-spacing:2.6px}}
      .quote{{fill:{theme['text']};font-size:{font_size}px;font-style:italic}}
      .author{{fill:{theme['accent']};font-size:13px;font-weight:700;letter-spacing:1.5px}}
      .source{{fill:{theme['muted']};font-size:10px;letter-spacing:.65px}}
      .marker{{fill:{theme['muted']};font-size:10px;letter-spacing:1.6px}}
      .pulse{{animation:pulse 3.2s ease-in-out infinite;transform-origin:1091px 73px}}
      .trace{{stroke-dasharray:3 9;animation:trace 12s linear infinite}}
      @keyframes pulse{{0%,100%{{opacity:.42;transform:scale(.82)}}50%{{opacity:1;transform:scale(1.1)}}}}
      @keyframes trace{{to{{stroke-dashoffset:-120}}}}
      @media (prefers-reduced-motion:reduce){{.pulse,.trace{{animation:none}}}}
    </style>
  </defs>
  <rect width="1200" height="396" rx="20" fill="{theme['background']}"/>
  <rect x="24" y="24" width="1152" height="348" rx="14" fill="{theme['panel']}" stroke="{theme['border']}"/>
  {paper_texture}
  <path d="M76 70H324" stroke="{theme['secondary']}" stroke-width="2"/>
  <text x="76" y="64" class="mono label">THOUGHT // {label}</text>
  <text x="1124" y="64" text-anchor="end" class="mono marker">{marker}</text>
  <g class="serif quote">
    <text>
{tspans}
    </text>
  </g>
  <text x="104" y="263" class="mono author">— {author}</text>
  {source_node}
  <g opacity=".8">
    <path class="trace" d="M918 224C967 144 1020 130 1089 75" fill="none" stroke="{theme['accent']}" stroke-opacity=".28"/>
    <circle cx="919" cy="224" r="4" fill="{theme['secondary']}"/>
    <circle cx="1008" cy="145" r="3" fill="{theme['accent']}"/>
    <circle cx="1091" cy="73" r="5" fill="{theme['accent']}" class="pulse" filter="url(#glow)"/>
    <circle cx="1091" cy="73" r="38" fill="none" stroke="{theme['accent']}" stroke-opacity=".12"/>
    <circle cx="1091" cy="73" r="50" fill="none" stroke="{theme['secondary']}" stroke-opacity=".1" stroke-dasharray="2 8"/>
  </g>
</svg>
'''


def main() -> int:
    args = parse_args()
    selection_date = args.date or datetime.now(timezone.utc).date()
    try:
        thoughts = load_thoughts()
        selected_index, thought = select_thought(thoughts, selection_date, args.index)
        rendered = {
            theme_name: render_svg(thought, theme_name, selected_index, len(thoughts))
            for theme_name in THEMES
        }
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    changed: list[Path] = []
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for theme_name, svg in rendered.items():
        destination = ASSET_DIR / f"thought-{theme_name}.svg"
        current = destination.read_text(encoding="utf-8") if destination.exists() else None
        if current != svg:
            changed.append(destination)
            if not args.check:
                destination.write_text(svg, encoding="utf-8", newline="\n")

    if args.check and changed:
        for path in changed:
            print(f"outdated: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    action = "checked" if args.check else "rendered"
    print(
        f"{action} {thought['id']} for {selection_date.isoformat()} "
        f"({selected_index + 1}/{len(thoughts)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
