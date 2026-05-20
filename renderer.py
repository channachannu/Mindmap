"""
renderer.py
-----------
Inject a mind map schema into template.html to produce
a self-contained HTML string ready for Streamlit or file export.

Usage:
  from renderer import render_mindmap
  html = render_mindmap(schema)                     # returns HTML string
  html = render_mindmap(schema, output_path="out.html")  # also writes file
"""

import json
import re
from pathlib import Path


# ── Config ────────────────────────────────────────────────────────────────────

TEMPLATE_PATH = Path(__file__).parent / "template.html"

# Map theme index → CSS variable name used in the JS
THEME_VAR_NAMES = ["--t1", "--t2", "--t3", "--t4", "--t5", "--t6", "--t7"]

# Default color palette (matches extractor.py)
THEME_COLORS = [
    "#E07A5F",  # coral
    "#6B8CAE",  # steel blue
    "#90BE6D",  # sage green
    "#FF6B6B",  # red
    "#56CFE1",  # teal
    "#C77DFF",  # purple
    "#F2CC8F",  # amber
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_color_vars(color_vars: dict) -> str:
    """
    Convert color_vars dict to CSS custom property declarations.

    Input:  {"--t1": "#E07A5F", "--t2": "#6B8CAE", ...}
    Output: "--t1: #E07A5F;\n  --t2: #6B8CAE;\n  ..."
    """
    if not color_vars:
        # Fallback — generate from defaults
        return "\n  ".join(
            f"{var}: {THEME_COLORS[i]};"
            for i, var in enumerate(THEME_VAR_NAMES[:7])
        )
    return "\n  ".join(
        f"{k}: {v};" for k, v in color_vars.items()
    )


def _build_schema_js(schema: dict) -> str:
    """
    Convert schema dict into JavaScript const declarations
    that the template expects: `themes`, `subclusters`, `lectures`.

    The template JS references these three globals directly.
    """
    themes     = schema.get("themes", [])
    lectures   = schema.get("lectures", [])

    # Build subclusters as a JS object keyed by theme id
    subclusters_obj = {}
    for theme in themes:
        tid = theme.get("id", "")
        subclusters_obj[tid] = theme.get("subclusters", [])

    # Assign color var references to themes and lectures
    # (extractor may have set _color_hex; template needs color as var(--tN))
    for i, theme in enumerate(themes):
        theme["color"] = f"var(--t{i+1})"

    # Assign lecture colors from their theme mapping
    lec_color_map = {}
    for i, theme in enumerate(themes):
        for sc in theme.get("subclusters", []):
            for lec_id in sc.get("lectures", []):
                lec_color_map[lec_id] = f"var(--t{i+1})"

    for lec in lectures:
        lec["color"] = lec_color_map.get(lec.get("id", ""), "var(--t1)")
        # Ensure chapter field exists (template uses lec.chapter)
        if "chapter" not in lec:
            lec["chapter"] = lec.get("source", "")

    # Serialise — use json.dumps for safety, then wrap in const declarations
    themes_json      = json.dumps(themes,          indent=2, ensure_ascii=False)
    subclusters_json = json.dumps(subclusters_obj, indent=2, ensure_ascii=False)
    lectures_json    = json.dumps(lectures,        indent=2, ensure_ascii=False)

    return f"""const themes = {themes_json};

const subclusters = {subclusters_json};

const lectures = {lectures_json};"""


def _build_meta(schema: dict) -> str:
    """Build the subtitle shown next to the subject name in the header."""
    parts = []
    src = schema.get("source_file", "")
    if src:
        parts.append(src)
    created = schema.get("created_at", "")
    if created:
        parts.append(created)
    n_lec = len(schema.get("lectures", []))
    if n_lec:
        parts.append(f"{n_lec} Lectures")
    return " · ".join(parts) if parts else "Mind Map"


# ── Main Renderer ─────────────────────────────────────────────────────────────

def render_mindmap(
    schema: dict,
    output_path: str | None = None,
    template_path: str | None = None,
) -> str:
    """
    Inject schema into template.html and return the rendered HTML string.

    Args:
        schema:        Full schema dict from extractor.extract_mindmap()
        output_path:   Optional path to write the rendered HTML file
        template_path: Override default template location

    Returns:
        Rendered HTML string (self-contained, no external deps except CDN)

    Raises:
        FileNotFoundError if template.html is missing
        ValueError if schema is missing required fields
    """
    # Load template
    tpl_path = Path(template_path) if template_path else TEMPLATE_PATH
    if not tpl_path.exists():
        raise FileNotFoundError(
            f"Template not found at {tpl_path}. "
            "Ensure template.html is in the same directory as renderer.py."
        )

    template = tpl_path.read_text(encoding="utf-8")

    # Validate schema minimally
    if not schema.get("themes"):
        raise ValueError("Schema has no themes — cannot render.")
    if not schema.get("lectures"):
        raise ValueError("Schema has no lectures — cannot render.")

    # Build injection values
    subject    = schema.get("subject", "Mind Map")
    meta       = _build_meta(schema)
    color_vars = _build_color_vars(schema.get("color_vars", {}))
    schema_js  = _build_schema_js(schema)

    # Inject
    html = template
    html = html.replace("{{SUBJECT}}",    subject)
    html = html.replace("{{META}}",       meta)
    html = html.replace("{{COLOR_VARS}}", color_vars)
    html = html.replace("{{SCHEMA_JSON}}", schema_js)

    # Verify all placeholders replaced
    remaining = re.findall(r"\{\{[A-Z_]+\}\}", html)
    if remaining:
        raise ValueError(f"Unreplaced placeholders in template: {remaining}")

    # Optionally write to file
    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")

    return html


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python renderer.py <schema.json> [output.html]")
        sys.exit(1)

    schema_path = sys.argv[1]
    out_path    = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        with open(schema_path) as f:
            schema = json.load(f)

        html = render_mindmap(schema, output_path=out_path)

        if out_path:
            print(f"Rendered: {out_path} ({len(html):,} chars)")
        else:
            print(f"Rendered OK ({len(html):,} chars) — pass output path to save")

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
