#!/usr/bin/env python3
"""
NeuroCodeForager — build the compiled database from the plain-text entries.

data/papers/*.txt is the SOURCE OF TRUTH: one plain-text file per paper,
easy to hand-edit (or drop in through the GitHub web UI, no code needed).
This script compiles all of them into data/entries.json, which is the single
file the actual website fetches at runtime.

Run it any time you add/edit a file in data/papers/:
    python build_index.py

You don't have to remember to run this yourself for every edit — see
.github/workflows/rebuild-index.yml, which runs it automatically whenever
something in data/papers/ changes and commits the updated entries.json.

File format — see data/papers/TEMPLATE.txt for a copy-paste starting point.
Single-line fields are "key: value". Multi-line fields (summary, tutorial_*,
abstract_long, extra_links) start with nothing after the colon and continue
until the next recognized key.

Every field beyond the core ones (title/journal/paper_url/etc.) is OPTIONAL —
fill in what you have. The detail page just hides sections with nothing to show.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PAPERS_DIR = REPO_ROOT / "data" / "papers"
ENTRIES_PATH = REPO_ROOT / "data" / "entries.json"

# Order doesn't matter for parsing, but this is also the whitelist of
# recognized keys — anything else in a file is ignored.
SINGLE_LINE_KEYS = [
    "title", "authors", "journal", "year", "date", "doi", "paper_url",
    "github_url", "website_url", "access_status", "category", "tags",
    "data_acquisition", "language", "animal", "gpu_required", "difficulty",
    "citation_count", "added_date", "verified",
    "subjects_count", "subjects_strains", "subjects_notes",
    "sample_data_text", "sample_data_url", "related_ids",
]
MULTI_LINE_KEYS = [
    "summary", "abstract_long", "tutorial", "tutorial_intro",
    "tutorial_steps", "tutorial_output", "extra_links",
]
ALL_KEYS = SINGLE_LINE_KEYS + MULTI_LINE_KEYS

KEY_LINE_RE = re.compile(r"^(" + "|".join(ALL_KEYS) + r"):\s*(.*)$")


def parse_entry_file(path: Path) -> dict:
    raw = {}
    current_key = None
    buffer = []

    def flush():
        if current_key is not None:
            raw[current_key] = "\n".join(buffer).strip()

    for line in path.read_text(encoding="utf-8").splitlines():
        m = KEY_LINE_RE.match(line)
        if m:
            flush()
            current_key = m.group(1)
            first_val = m.group(2)
            buffer = [first_val] if first_val else []
        else:
            if current_key is not None:
                buffer.append(line)
    flush()

    tags = [t.strip() for t in raw.get("tags", "").split(",") if t.strip()]
    categories = [c.strip() for c in raw.get("category", "").split(",") if c.strip()]
    year_raw = raw.get("year", "").strip()
    citation_raw = raw.get("citation_count", "").strip()
    access_status = raw.get("access_status", "").strip() or "paywall_restricted"
    verified_raw = raw.get("verified", "").strip().lower()
    related_ids = [r.strip() for r in raw.get("related_ids", "").split(",") if r.strip()]

    # extra_links: one "Label | URL" per line
    extra_links = []
    for line in raw.get("extra_links", "").splitlines():
        if "|" in line:
            label, url = line.split("|", 1)
            label, url = label.strip(), url.strip()
            if label and url:
                extra_links.append({"label": label, "url": url})

    # tutorial_steps: one step per line -> list; if absent, fall back to the
    # older flat "tutorial" field as a single pre-formatted block
    tutorial_steps = [s.strip() for s in raw.get("tutorial_steps", "").splitlines() if s.strip()]

    return {
        "id": path.stem,  # filename without extension, e.g. "2026-08-18-cellexplorer"
        "title": raw.get("title", "").strip(),
        "authors": raw.get("authors", "").strip(),
        "journal": raw.get("journal", "").strip(),
        "year": int(year_raw) if year_raw.isdigit() else (year_raw or None),
        "date": raw.get("date", "").strip(),
        "doi": raw.get("doi", "").strip(),
        "paper_url": raw.get("paper_url", "").strip(),
        "website_url": raw.get("website_url", "").strip(),
        "access_status": access_status if access_status in ("open_access", "paywall_restricted") else "paywall_restricted",
        "citation_count": int(citation_raw) if citation_raw.isdigit() else None,
        "category": categories[0] if categories else "",
        "categories": categories,
        "tags": tags,
        "summary": raw.get("summary", "").strip(),
        "abstract_long": raw.get("abstract_long", "").strip(),
        "data_acquisition": raw.get("data_acquisition", "").strip() or "Not specified",
        "language": raw.get("language", "").strip(),
        "animal": raw.get("animal", "").strip() or "Not applicable",
        "gpu_required": raw.get("gpu_required", "").strip(),
        "difficulty": raw.get("difficulty", "").strip(),
        "subjects": {
            "count": raw.get("subjects_count", "").strip(),
            "strains": raw.get("subjects_strains", "").strip(),
            "notes": raw.get("subjects_notes", "").strip(),
        },
        "tutorial": raw.get("tutorial", "").strip(),
        "tutorial_intro": raw.get("tutorial_intro", "").strip(),
        "tutorial_steps": tutorial_steps,
        "tutorial_output": raw.get("tutorial_output", "").strip(),
        "sample_data": {
            "text": raw.get("sample_data_text", "").strip(),
            "url": raw.get("sample_data_url", "").strip(),
        },
        "code": {
            "repo_url": raw.get("github_url", "").strip(),
            "platform": "github" if "github.com" in raw.get("github_url", "") else "other",
        },
        "extra_links": extra_links,
        "related_ids": related_ids,
        "added_date": raw.get("added_date", "").strip(),
        "added_by": "manual",
        "verified": verified_raw != "false",  # defaults to true unless explicitly set to false
    }


def build():
    if not PAPERS_DIR.exists():
        print(f"No {PAPERS_DIR} folder found.")
        sys.exit(1)

    files = sorted(p for p in PAPERS_DIR.glob("*.txt") if p.name != "TEMPLATE.txt")
    if not files:
        print(f"No entry files found in {PAPERS_DIR} (besides TEMPLATE.txt).")
        return []

    entries = []
    for f in files:
        try:
            entries.append(parse_entry_file(f))
        except Exception as e:
            print(f"  Skipping {f.name} — couldn't parse it: {e}")

    ENTRIES_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    print(f"Built {ENTRIES_PATH} from {len(entries)} file(s) in {PAPERS_DIR}")
    return entries


if __name__ == "__main__":
    build()
