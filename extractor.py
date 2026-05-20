from dotenv import load_dotenv
load_dotenv()
"""
extractor.py
------------
PDF → structured mind map schema via Claude API.

Pipeline:
  1. Extract text from PDF (pypdf)
  2. Chunk by section/lecture boundaries
  3. Send to Claude with strict JSON schema prompt
  4. Validate + return structured dict

Usage:
  from extractor import extract_mindmap
  schema = extract_mindmap("path/to/file.pdf")
"""

import re
import json
import uuid
from datetime import datetime
from pathlib import Path
import os
from pypdf import PdfReader
import anthropic


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_CONTENT_CHARS = 12000   # ~3k tokens — enough for 8-15 lectures
MODEL             = "claude-sonnet-4-5"


# ── JSON Schema prompt ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a curriculum analyst. Your job is to extract a structured knowledge map from academic course content.

Output ONLY valid JSON — no preamble, no explanation, no markdown fences.

The JSON must match this exact schema:
{
  "subject": "Full subject name",
  "themes": [
    {
      "id": "t1",
      "name": "Theme Name (2-3 words)",
      "icon": "single unicode symbol (◎ ◈ ◇ ◉ ◐ ▣ ◆)",
      "sub": "subtopic1 · subtopic2 · subtopic3",
      "subclusters": [
        {
          "id": "t1s1",
          "name": "Subcluster Name",
          "tags": ["tag1", "tag2", "tag3"],
          "definition": "Clear 2-3 sentence definition of this concept cluster.",
          "keypoints": [
            "Specific point 1",
            "Specific point 2",
            "Specific point 3"
          ],
          "example": "A concrete, specific example from the course content.",
          "formula": "Key formula or null if not applicable",
          "lectures": ["L01", "L02"]
        }
      ]
    }
  ],
  "lectures": [
    {
      "id": "L01",
      "num": "L01",
      "title": "Lecture Title",
      "tags": ["tag1", "tag2"],
      "concepts": [
        "Key concept covered in this lecture",
        "Another key concept"
      ],
      "formula": "Key formula from this lecture or null"
    }
  ]
}

Rules:
- 4 to 6 themes maximum
- 2 to 4 subclusters per theme
- 4 to 8 keypoints per subcluster
- Each subcluster must reference 1-2 lecture IDs
- Formulae: include only where mathematically or analytically relevant, otherwise null
- Examples: must be concrete and grounded in the actual content, not generic
- Lecture IDs: use L01, L02... format, zero-padded to match the number of lectures
- Tags: short, scannable keywords (2-4 per item)
- Do not invent content — only use what is present in the slides"""

USER_PROMPT_TEMPLATE = """Extract a structured knowledge map from the following course content.

Subject hint (from filename): {filename}
Total slides/pages detected: {page_count}

CONTENT:
{content}"""


# ── PDF Extraction ────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: str) -> tuple[str, int]:
    """
    Extract raw text from a PDF.
    Returns (text, page_count).
    Raises ValueError if text extraction fails or PDF appears scanned.
    """
    reader = PdfReader(pdf_path)
    page_count = len(reader.pages)

    pages_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(f"[Page {i+1}]\n{text.strip()}")

    full_text = "\n\n".join(pages_text)

    if len(full_text.strip()) < 100:
        raise ValueError(
            "Could not extract text from this PDF. "
            "It may be a scanned document. Please use a text-based PDF."
        )

    return full_text, page_count


def detect_lecture_boundaries(text: str) -> list[dict]:
    """
    Detect lecture/chapter boundaries from common patterns.
    Returns list of {num, start_char} dicts.
    """
    patterns = [
        r"Lecture\s+No\.?\s*(\d+)",
        r"Chapter\s+(\d+)",
        r"Module\s+(\d+)",
        r"Unit\s+(\d+)",
        r"Week\s+(\d+)",
        r"Session\s+(\d+)",
        r"Topic\s+(\d+)",
    ]

    boundaries = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            num = int(match.group(1))
            boundaries.append({"num": num, "start": match.start()})

    if not boundaries:
        return []

    # Deduplicate — keep first occurrence of each lecture number
    seen = set()
    unique = []
    for b in sorted(boundaries, key=lambda x: x["start"]):
        if b["num"] not in seen:
            seen.add(b["num"])
            unique.append(b)

    return sorted(unique, key=lambda x: x["num"])


def chunk_content(text: str, max_chars: int = MAX_CONTENT_CHARS) -> str:
    """
    Intelligently truncate content to fit within token budget.
    Preserves lecture boundaries where possible.
    """
    if len(text) <= max_chars:
        return text

    boundaries = detect_lecture_boundaries(text)

    if boundaries:
        # Take content up to max_chars, ending at a lecture boundary
        truncated = text[:max_chars]
        # Find last complete lecture within budget
        last_boundary = None
        for b in boundaries:
            if b["start"] < max_chars:
                last_boundary = b["start"]

        if last_boundary:
            truncated = text[:last_boundary]

        return truncated + f"\n\n[Content truncated — {len(text)} chars total, showing first {len(truncated)} chars]"

    # No boundaries found — simple truncation at paragraph boundary
    truncated = text[:max_chars]
    last_para = truncated.rfind("\n\n")
    if last_para > max_chars * 0.7:
        truncated = truncated[:last_para]

    return truncated + f"\n\n[Content truncated — showing first {len(truncated)} of {len(text)} chars]"


# ── Claude Extraction ─────────────────────────────────────────────────────────

def call_claude(content: str, filename: str, page_count: int) -> dict:
    """
    Send content to Claude and return parsed JSON schema.
    Raises ValueError if response is not valid JSON or schema is malformed.
    """
    #client = anthropic.Anthropic()
    import os
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    user_prompt = USER_PROMPT_TEMPLATE.format(
        filename=filename,
        page_count=page_count,
        content=content,
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=9000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if Claude added them despite instructions
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\n\nRaw output:\n{raw[:500]}")

    return data


# ── Schema Validation ─────────────────────────────────────────────────────────

def validate_schema(data: dict) -> list[str]:
    """
    Validate extracted schema. Returns list of warnings (not errors).
    Schema is accepted even with warnings — warnings surface in the UI.
    """
    warnings = []

    if "subject" not in data or not data["subject"]:
        warnings.append("Subject name missing — using filename as fallback.")

    themes = data.get("themes", [])
    if len(themes) < 2:
        warnings.append(f"Only {len(themes)} theme(s) detected — consider a more structured PDF.")
    if len(themes) > 7:
        warnings.append(f"{len(themes)} themes detected — map may be dense.")

    for t in themes:
        scs = t.get("subclusters", [])
        if not scs:
            warnings.append(f"Theme '{t.get('name', '?')}' has no subclusters.")
        for sc in scs:
            if not sc.get("definition"):
                warnings.append(f"Subcluster '{sc.get('name', '?')}' missing definition.")
            if not sc.get("keypoints"):
                warnings.append(f"Subcluster '{sc.get('name', '?')}' has no keypoints.")
            if not sc.get("example"):
                warnings.append(f"Subcluster '{sc.get('name', '?')}' missing example.")

    lectures = data.get("lectures", [])
    if not lectures:
        warnings.append("No lectures extracted — PDF may lack clear lecture structure.")

    return warnings


# ── Colour Assignment ─────────────────────────────────────────────────────────

THEME_COLORS = [
    "#E07A5F",  # coral
    "#6B8CAE",  # blue
    "#90BE6D",  # green
    "#FF6B6B",  # red
    "#56CFE1",  # teal
    "#C77DFF",  # purple
    "#F2CC8F",  # amber
]

LECTURE_COLORS = {
    "t1": "#E07A5F",
    "t2": "#6B8CAE",
    "t3": "#90BE6D",
    "t4": "#FF6B6B",
    "t5": "#56CFE1",
    "t6": "#C77DFF",
    "t7": "#F2CC8F",
}


def assign_colors(data: dict) -> dict:
    """
    Assign colors to themes and derive lecture colors from their theme mapping.
    Mutates data in place, returns it.
    """
    # Build lecture → theme mapping
    lec_theme_map = {}
    for i, theme in enumerate(data.get("themes", [])):
        color = THEME_COLORS[i % len(THEME_COLORS)]
        theme["color"] = f"var(--t{i+1})"
        theme["_color_hex"] = color

        for sc in theme.get("subclusters", []):
            for lec_id in sc.get("lectures", []):
                lec_theme_map[lec_id] = f"var(--t{i+1})"

    # Assign colors to lectures
    for lec in data.get("lectures", []):
        lec["color"] = lec_theme_map.get(lec["id"], "var(--t1)")

    return data


# ── Main Entry Point ──────────────────────────────────────────────────────────

def extract_mindmap(pdf_path: str) -> dict:
    """
    Full pipeline: PDF → validated mind map schema dict.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        dict with keys: id, subject, created_at, source_file,
                        themes, lectures, warnings, color_vars
    """
    path = Path(pdf_path)
    filename = path.stem

    # Step 1: Extract PDF text
    raw_text, page_count = extract_pdf_text(pdf_path)

    # Step 2: Chunk to fit token budget
    content = chunk_content(raw_text)

    # Step 3: Claude extraction
    data = call_claude(content, filename, page_count)

    # Step 4: Validate
    warnings = validate_schema(data)

    # Step 5: Assign colors
    data = assign_colors(data)

    # Step 6: Build CSS color vars for themes
    color_vars = {}
    for i, theme in enumerate(data.get("themes", [])):
        color_vars[f"--t{i+1}"] = THEME_COLORS[i % len(THEME_COLORS)]

    # Step 7: Attach metadata
    data["id"]          = str(uuid.uuid4())[:8]
    data["created_at"]  = datetime.now().strftime("%Y-%m-%d %H:%M")
    data["source_file"] = path.name
    data["warnings"]    = warnings
    data["color_vars"]  = color_vars
    data.setdefault("subject", filename.replace("_", " ").title())

    return data


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extractor.py path/to/file.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"Extracting: {pdf_path}")

    try:
        schema = extract_mindmap(pdf_path)
        print(f"\nSubject:  {schema['subject']}")
        print(f"Themes:   {len(schema['themes'])}")
        print(f"Lectures: {len(schema['lectures'])}")
        print(f"Map ID:   {schema['id']}")

        if schema["warnings"]:
            print(f"\nWarnings ({len(schema['warnings'])}):")
            for w in schema["warnings"]:
                print(f"  ⚠ {w}")

        for t in schema["themes"]:
            print(f"\n  [{t['id']}] {t['name']}")
            for sc in t["subclusters"]:
                print(f"       └── {sc['name']} [{', '.join(sc['lectures'])}]")

        out_path = f"/tmp/{schema['id']}_schema.json"
        with open(out_path, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"\nSaved to: {out_path}")

    except ValueError as e:
        print(f"\nExtraction failed: {e}")
        sys.exit(1)
