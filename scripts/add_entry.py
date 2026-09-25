#!/usr/bin/env python3
"""
Interactive helper to add one entry to the database.

Usage:
    cd scripts
    pip install -r requirements.txt --break-system-packages   # first time only
    python add_entry.py

This writes a new plain-text file into data/papers/ (the source of truth —
see data/papers/TEMPLATE.txt for the format) and then rebuilds
data/entries.json from all of them, so the site picks it up immediately.

It fetches Open Graph (og:*) metadata from the paper URL just to suggest
sensible defaults for title/journal/summary — you can override any of them.
"""
import re
import sys
from datetime import date
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip install -r requirements.txt --break-system-packages")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
import build_index

PAPERS_DIR = Path(__file__).parent.parent / "data" / "papers"

CATEGORIES = [
    "image-analysis",
    "statistical-analysis",
    "automated-behavioral-tracking",
    "electrophysiology",
    "brain-imaging",
    "gene-protein-analysis",
    "spatial-omics",
    "neural-networks",
]


def fetch_og(url):
    """Pull og:title / og:description / og:site_name from a URL, just for suggestions."""
    if not url:
        return {"title": "", "description": "", "site_name": ""}
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        def og(prop):
            tag = soup.find("meta", property=f"og:{prop}")
            return tag["content"].strip() if tag and tag.get("content") else ""

        return {
            "title": og("title") or (soup.title.string.strip() if soup.title else ""),
            "description": og("description"),
            "site_name": og("site_name"),
        }
    except Exception as e:
        print(f"  (couldn't fetch metadata from {url}: {e})")
        return {"title": "", "description": "", "site_name": ""}


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or default


def slugify(text):
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:40] or "entry"


def main():
    print("=== NeuroCodeForager — add entry ===\n")

    paper_url = ask("Paper URL")
    print("Fetching paper metadata for suggestions...")
    paper_embed = fetch_og(paper_url)

    title = ask("Title", paper_embed["title"])
    authors = ask("Authors (Last F., Last F. — comma separated)")
    journal = ask("Journal / venue", paper_embed["site_name"])
    year = ask("Year", str(date.today().year))
    doi = ask("DOI (optional, no https://)")

    print("\nCategories:")
    for i, c in enumerate(CATEGORIES, 1):
        print(f"  {i}. {c}")
    cat_idx_raw = ask("Category number(s) — comma-separated if more than one applies")
    cat_indices = [i.strip() for i in cat_idx_raw.split(",") if i.strip()]
    category = ", ".join(
        CATEGORIES[int(i) - 1] for i in cat_indices
        if i.isdigit() and 1 <= int(i) <= len(CATEGORIES)
    )

    tags_raw = ask("Tags (comma separated — include technique synonyms/brands to help search)")
    access_status = ""
    while access_status not in ("open_access", "paywall_restricted"):
        raw = ask("Access status — 1) open access  2) paywall restricted", "1")
        access_status = "open_access" if raw.strip() == "1" else "paywall_restricted" if raw.strip() == "2" else ""

    summary = ask("Short summary for the search card (1-2 sentences)", paper_embed["description"])
    data_acquisition = ask("Data acquisition method (be specific, incl. brand if known)")
    animal = ask("Animal / species (or 'Not applicable')", "Not applicable")
    repo_url = ask("Code repository URL (GitHub/GitLab/etc, optional)")
    language = ask("Primary programming language")
    difficulty = ask("Difficulty (beginner/intermediate/advanced)", "intermediate")
    citation_count = ask("Citation count (optional — leave blank if unknown)")

    print("\nTutorial — input data, numbered steps (explain what each does, not just the command),")
    print("outputs and what's in them. Aim for real detail (~450-700 words) — optional, can fill in later.")
    print("Type it out, end with an empty line:")
    tutorial_lines = []
    while True:
        line = input()
        if not line:
            break
        tutorial_lines.append(line)
    tutorial = "\n".join(tutorial_lines)

    added_date = date.today().isoformat()
    filename = f"{added_date}-{slugify(title)}.txt"
    filepath = PAPERS_DIR / filename

    content = f"""title: {title}
authors: {authors}
journal: {journal}
year: {year}
doi: {doi}
paper_url: {paper_url}
github_url: {repo_url}
access_status: {access_status}
category: {category}
tags: {tags_raw}
data_acquisition: {data_acquisition}
language: {language}
animal: {animal}
difficulty: {difficulty}
citation_count: {citation_count}
added_date: {added_date}

summary:
{summary}

tutorial:
{tutorial}
"""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    print(f"\nWrote {filepath}")

    build_index.build()
    print("Commit and push data/papers/ and data/entries.json to publish it on the live site.")


if __name__ == "__main__":
    main()
