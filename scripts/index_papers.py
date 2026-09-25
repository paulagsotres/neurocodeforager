#!/usr/bin/env python3
"""
NeuroCodeForager — automated indexing pipeline.

Intended to run on a schedule (e.g. weekly via GitHub Actions or a local cron)
against a queue of already-discovered {paper_url, github_url} pairs. Finding
those pairs (the "input" side — crawling journals/preprint servers for code
availability links) is a separate, future script; this one only handles
ENRICHING and INDEXING pairs you already have.

Pipeline per entry:
    1. Resolve DOI from the paper URL
    2. Open access status       -> explicit value in the queue if you set
       one (you'll know this per journal), else guessed from the domain
    3. Citation count           -> Semantic Scholar API
    4. Title, authors, journal, year -> Crossref API (falls back to Open
       Graph tags on the paper page if there's no DOI)
    5. Repo README + language   -> GitHub API
    6. Category, tags, summary, data acquisition method, animal, tutorial
       -> Claude (Anthropic API), given the abstract + README as context.
       If the paper is paywalled, Claude is told to lean on the repo/README
       and the abstract only, rather than assuming full-text access.

Each processed paper is written as a plain-text file into data/papers/ (the
same hand-editable format add_entry.py produces — see
data/papers/TEMPLATE.txt) with verified: false, then data/entries.json (the
file the live site actually reads) is rebuilt from all of them.

Usage:
    export ANTHROPIC_API_KEY=...
    python index_papers.py --queue data/pending_papers.json

pending_papers.json format (the "input" queue you'll feed manually or from
the future discovery script):
    [
      {
        "paper_url": "https://doi.org/10.xxxx/...",
        "github_url": "https://github.com/user/repo",
        "access_status": "open_access"   // optional — omit to guess from domain
      },
      ...
    ]
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    from anthropic import Anthropic
except ImportError:
    print("Missing dependency. Run: pip install -r requirements.txt --break-system-packages")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
import build_index

REPO_ROOT = Path(__file__).parent.parent
PAPERS_DIR = REPO_ROOT / "data" / "papers"

# Update this if Anthropic's current recommended model has changed —
# check https://docs.claude.com for the latest model strings.
CLAUDE_MODEL = "claude-sonnet-5"

# Domains known to be open access by default. Extend this as you map out
# which journals/sources you're pulling from — or just set "access_status"
# explicitly per entry in the input queue (data/pending_papers.json) when
# you already know it, which always takes priority over this guess.
OPEN_ACCESS_DOMAINS = [
    "biorxiv.org",
    "medrxiv.org",
    "elifesciences.org",
    "journals.plos.org",
    "ncbi.nlm.nih.gov/pmc",
    "pmc.ncbi.nlm.nih.gov",
    "frontiersin.org",
]

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

HEADERS = {"User-Agent": "Mozilla/5.0 (NeuroCodeForager indexing bot)"}


# ---------------------------------------------------------------------------
# Step 1: DOI resolution (kept for citation lookup + reference; no longer
# used for an open-access API call)
# ---------------------------------------------------------------------------
def extract_doi(url: str) -> str | None:
    """Pull a DOI out of a URL if one is present (doi.org links, or a doi=
    query param some publishers use)."""
    m = re.search(r"doi\.org/(10\.\d{4,9}/[^\s?#]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]doi=(10\.\d{4,9}/[^\s&]+)", url)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Step 2: Open access status
#
# Two states only: "open_access" or "paywall_restricted". This determines
# how much text the AI classification step gets to work with — open access
# lets us use the fetched description more liberally as "from the paper";
# paywalled entries fall back to whatever the abstract (via Open Graph tags,
# which publishers almost always set regardless of paywall) and the GitHub
# README give us.
# ---------------------------------------------------------------------------
def determine_access_status(paper_url: str, explicit: str | None = None) -> str:
    if explicit in ("open_access", "paywall_restricted"):
        return explicit
    domain = paper_url.lower()
    if any(d in domain for d in OPEN_ACCESS_DOMAINS):
        return "open_access"
    return "paywall_restricted"


# ---------------------------------------------------------------------------
# Step 3: Citation count
# ---------------------------------------------------------------------------
def fetch_citation_count(doi: str | None) -> int | None:
    if not doi:
        return None
    try:
        r = requests.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "citationCount"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("citationCount")
    except Exception as e:
        print(f"  (Semantic Scholar lookup failed: {e})")
    return None


# ---------------------------------------------------------------------------
# Step 4: Open Graph metadata (paper + repo link previews)
# ---------------------------------------------------------------------------
def fetch_og(url: str) -> dict:
    try:
        r = requests.get(url, timeout=10, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")

        def og(prop):
            tag = soup.find("meta", property=f"og:{prop}")
            return tag["content"].strip() if tag and tag.get("content") else ""

        return {
            "title": og("title") or (soup.title.string.strip() if soup.title else ""),
            "description": og("description"),
            "image": og("image"),
            "site_name": og("site_name"),
        }
    except Exception as e:
        print(f"  (couldn't fetch OG metadata from {url}: {e})")
        return {"title": "", "description": "", "image": "", "site_name": ""}


# ---------------------------------------------------------------------------
# Step 4b: Crossref (authors, journal, year) — far more reliable for these
# fields than scraping OG tags, and needed for the "Cite" (BibTeX) button.
# ---------------------------------------------------------------------------
def fetch_crossref(doi: str | None) -> dict:
    if not doi:
        return {"authors": "", "journal": "", "year": None, "title": ""}
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return {"authors": "", "journal": "", "year": None, "title": ""}
        msg = r.json().get("message", {})
        authors_list = msg.get("author", [])
        authors = ", ".join(
            f"{a.get('family', '')} {a.get('given', '')[:1]}.".strip()
            for a in authors_list if a.get("family")
        )
        journal = (msg.get("container-title") or [""])[0]
        year = None
        date_parts = msg.get("published", {}).get("date-parts", [[None]])
        if date_parts and date_parts[0] and date_parts[0][0]:
            year = date_parts[0][0]
        title = (msg.get("title") or [""])[0]
        return {"authors": authors, "journal": journal, "year": year, "title": title}
    except Exception as e:
        print(f"  (Crossref lookup failed: {e})")
        return {"authors": "", "journal": "", "year": None, "title": ""}


# ---------------------------------------------------------------------------
# Step 5: GitHub repo metadata + README
# ---------------------------------------------------------------------------
def parse_github_repo(github_url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", github_url)
    if not m:
        return None
    return m.group(1), m.group(2).removesuffix(".git")


def fetch_github_data(github_url: str) -> dict:
    parsed = parse_github_repo(github_url)
    if not parsed:
        return {"language": "", "description": "", "readme": ""}
    owner, repo = parsed

    language, description = "", ""
    try:
        r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            language = data.get("language", "") or ""
            description = data.get("description", "") or ""
    except Exception as e:
        print(f"  (GitHub repo metadata failed: {e})")

    readme = ""
    try:
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers={**HEADERS, "Accept": "application/vnd.github.raw"},
            timeout=10,
        )
        if r.status_code == 200:
            readme = r.text[:6000]  # cap length fed into the LLM prompt
    except Exception as e:
        print(f"  (GitHub README fetch failed: {e})")

    return {"language": language, "description": description, "readme": readme}


# ---------------------------------------------------------------------------
# Step 6: AI classification + tutorial (Claude)
# ---------------------------------------------------------------------------
CLASSIFY_PROMPT = """You are helping index a neuroscience open-source tool for a search database.

Paper title: {title}
Paper abstract: {abstract}
Access status: {access_status}
{access_note}

GitHub repo description: {repo_description}
GitHub repo language (detected): {repo_language}
GitHub README (may be partial):
---
{readme}
---

Categories to choose exactly one from: {categories}

Respond with ONLY a JSON object (no markdown fences, no preamble), matching this schema exactly:

{{
  "category": "<one slug from the categories list, or several comma-separated if the paper genuinely spans more than one — e.g. 'electrophysiology, brain-imaging'>",
  "tags": ["<8 to 12 specific search keywords: techniques, brand names, synonyms, related concepts>"],
  "summary": "<1-2 sentence plain-language summary of what the tool does, for a compact search result card>",
  "data_acquisition": "<the specific data acquisition method, including brand/model if identifiable from the text, e.g. 'Extracellular electrophysiology — silicon probes / Neuropixels (IMEC)'. If not applicable/identifiable, use 'Not specified'.>",
  "language": "<primary programming language, from repo data>",
  "animal": "<species used, e.g. 'Mouse, rat'. If not applicable (e.g. a general-purpose statistical tool), use 'Not applicable'.>",
  "difficulty": "<beginner | intermediate | advanced>",
  "tutorial": "<a detailed step-by-step tutorial, 450-700 words, covering: (1) what input data format is expected and how to prepare/organize it, (2) numbered installation and setup steps including any dependencies or environment requirements, (3) each analysis step with enough detail that someone unfamiliar with the tool could follow along (explain what each command/parameter does, not just what to type), (4) what outputs the user gets and what the output fields/files mean, (5) any common gotchas or notes worth flagging. Use the README content to make this concrete and accurate — do not invent function names or commands that aren't grounded in the README provided. If the README doesn't have enough detail to reach this length accurately, write what's genuinely supported and note briefly that further detail should come from the repo's own docs — do not pad with generic filler.>"
}}
"""

ACCESS_NOTES = {
    "open_access": "You have the full abstract text above to work with for the summary.",
    "paywall_restricted": (
        "This paper is paywalled — you only have the abstract (not the full text) plus "
        "whatever the GitHub repo/README say. Base the summary mainly on the repo "
        "description/README, and keep any paper-derived claims limited to what's in the "
        "abstract above. Do not infer methodological details that aren't stated in either source."
    ),
}


def classify_with_claude(client: Anthropic, title: str, abstract: str, access_status: str, github_data: dict) -> dict:
    prompt = CLASSIFY_PROMPT.format(
        title=title,
        abstract=abstract or "(not available)",
        access_status=access_status,
        access_note=ACCESS_NOTES.get(access_status, ""),
        repo_description=github_data.get("description") or "(not available)",
        repo_language=github_data.get("language") or "(not detected)",
        readme=github_data.get("readme") or "(not available)",
        categories=", ".join(CATEGORIES),
    )
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  (Claude response wasn't valid JSON: {e})")
        print(f"  Raw response: {text[:500]}")
        return {}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def process_entry(client: Anthropic, paper_url: str, github_url: str, access_status_override: str | None = None) -> dict | None:
    print(f"Processing: {paper_url}")
    doi = extract_doi(paper_url)

    access_status = determine_access_status(paper_url, access_status_override)
    citation_count = fetch_citation_count(doi)
    paper_embed = fetch_og(paper_url)
    crossref = fetch_crossref(doi)
    github_data = fetch_github_data(github_url)

    title = crossref.get("title") or paper_embed.get("title", "")
    abstract = paper_embed.get("description", "")

    ai_result = classify_with_claude(
        client,
        title=title,
        abstract=abstract,
        access_status=access_status,
        github_data=github_data,
    )
    if not ai_result:
        print("  Skipping entry — AI classification failed.")
        return None

    return {
        "title": title,
        "authors": crossref.get("authors", ""),
        "journal": crossref.get("journal") or paper_embed.get("site_name", ""),
        "year": crossref.get("year"),
        "doi": doi or "",
        "paper_url": paper_url,
        "github_url": github_url,
        "access_status": access_status,
        "citation_count": citation_count,
        "category": ai_result.get("category", ""),
        "tags": ai_result.get("tags", []),
        "summary": ai_result.get("summary", ""),
        "data_acquisition": ai_result.get("data_acquisition", ""),
        "language": ai_result.get("language", github_data.get("language", "")),
        "animal": ai_result.get("animal", ""),
        "difficulty": ai_result.get("difficulty", ""),
        "tutorial": ai_result.get("tutorial", ""),
        "added_date": date.today().isoformat(),
        "verified": False,  # auto-added entries start unverified until you spot-check them
    }


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:40] or "entry"


def write_entry_txt(entry: dict) -> Path:
    """Writes one entry as a plain-text file into data/papers/ — the same
    hand-editable format add_entry.py produces. This is what makes
    data/papers/ the single source of truth regardless of whether an entry
    came from this automated pipeline or was typed in by hand."""
    filename = f"{entry['added_date']}-{slugify(entry['title'])}.txt"
    filepath = PAPERS_DIR / filename
    content = f"""title: {entry['title']}
authors: {entry['authors']}
journal: {entry['journal']}
year: {entry['year'] or ''}
doi: {entry['doi']}
paper_url: {entry['paper_url']}
github_url: {entry['github_url']}
access_status: {entry['access_status']}
category: {entry['category']}
tags: {', '.join(entry['tags'])}
data_acquisition: {entry['data_acquisition']}
language: {entry['language']}
animal: {entry['animal']}
difficulty: {entry['difficulty']}
citation_count: {entry['citation_count'] if entry['citation_count'] is not None else ''}
added_date: {entry['added_date']}
verified: {"true" if entry['verified'] else "false"}

summary:
{entry['summary']}

tutorial:
{entry['tutorial']}
"""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return filepath


REVIEWS_DIR = REPO_ROOT / "reviews"

_REVIEW_CSS = """
:root{--ink:#1B1D16;--paper:#F6F1E4;--paper-dim:#EBE3CD;--teal:#1B8C82;--teal-deep:#146860;
--teal-soft:#DCEEEA;--amber:#B5713F;--amber-soft:#F3E4D6;--muted:#5b5b4e;--faint:#9b9585;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Stack Sans Text',sans-serif;background:var(--paper);color:var(--ink);line-height:1.5;padding:32px;}
a{color:inherit;text-decoration:none;}
h1{font-family:'Fraunces',serif;font-weight:500;font-size:24px;margin-bottom:6px;}
.sub{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--faint);margin-bottom:28px;}
.card{background:#fff;border:1px solid var(--paper-dim);border-radius:12px;padding:20px 22px;margin-bottom:16px;}
.card-title{font-family:'Fraunces',serif;font-weight:500;font-size:18px;display:block;margin-bottom:8px;}
.tag-row{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px;}
.tag{font-family:'IBM Plex Mono',monospace;font-size:10.5px;padding:3px 9px;border-radius:999px;}
.tag.cat{background:var(--amber-soft);color:var(--amber);}
.tag.oa{background:var(--teal-soft);color:var(--teal-deep);}
.tag.paywall{background:var(--amber-soft);color:var(--amber);}
.tag.plain{background:var(--paper);color:var(--muted);border:1px solid var(--paper-dim);}
.tag.unverified{background:#f6d6d6;color:#a6472a;}
.card-body{display:grid;grid-template-columns:1fr 1.5fr auto;border-top:1px solid var(--paper-dim);padding-top:16px;}
.col{padding:0 20px;}
.col:first-child{padding-left:0;}
.col:not(:last-child){border-right:1px solid var(--paper-dim);}
.meta-row{margin-bottom:10px;}
.meta-row .k{font-family:'IBM Plex Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin-bottom:2px;}
.meta-row .v{font-size:13px;font-weight:500;}
.summary-text{font-size:13.5px;color:var(--muted);line-height:1.6;}
.link-col{display:flex;flex-direction:column;gap:8px;min-width:150px;}
.link-btn{display:flex;align-items:center;gap:7px;font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:500;
padding:7px 12px;border-radius:7px;border:1px solid var(--paper-dim);white-space:nowrap;background:none;cursor:pointer;
color:var(--ink);width:100%;text-align:left;}
.link-btn:hover{border-color:var(--teal);color:var(--teal-deep);}
.link-btn.tutorial{background:var(--teal-soft);border-color:var(--teal-soft);color:var(--teal-deep);}
.overlay{display:none;position:fixed;inset:0;background:rgba(27,29,22,0.45);align-items:center;justify-content:center;padding:24px;z-index:100;}
.overlay.open{display:flex;}
.popup{background:#fff;border-radius:14px;max-width:560px;width:100%;max-height:82vh;overflow-y:auto;padding:26px 28px;position:relative;}
.popup-close{position:absolute;top:16px;right:16px;width:28px;height:28px;border-radius:50%;border:none;background:var(--paper);
color:var(--muted);cursor:pointer;font-size:16px;}
.popup-title{font-family:'Fraunces',serif;font-weight:500;font-size:17px;margin-bottom:14px;padding-right:30px;}
.popup-text{font-size:13.5px;color:var(--muted);line-height:1.7;white-space:pre-wrap;}
@media (max-width:760px){.card-body{grid-template-columns:1fr;}.col{padding:0 0 14px;border-right:none !important;
border-bottom:1px solid var(--paper-dim);}}
"""


def _card_html(entry: dict, idx: int) -> str:
    access_tag = (
        '<span class="tag oa">open access</span>'
        if entry.get("access_status") == "open_access"
        else '<span class="tag paywall">paywall restricted</span>'
    )
    cat = entry.get("category", "")
    tags_extra = "".join(f'<span class="tag plain">{t}</span>' for t in entry.get("tags", [])[:4])
    citations = entry.get("citation_count")
    citations_str = f"{citations} citations" if citations is not None else "citations: —"

    return f"""
<div class="card">
  <a class="card-title" href="{entry.get('paper_url', '#')}" target="_blank" rel="noopener">{entry.get('title', '(untitled)')}</a>
  <div class="tag-row">
    <span class="tag cat">{cat}</span>
    {access_tag}
    <span class="tag plain">{citations_str}</span>
    <span class="tag unverified">unverified</span>
    {tags_extra}
  </div>
  <div class="card-body">
    <div class="col">
      <div class="meta-row"><div class="k">Data acquisition</div><div class="v">{entry.get('data_acquisition', '')}</div></div>
      <div class="meta-row"><div class="k">Language</div><div class="v">{entry.get('language', '')}</div></div>
      <div class="meta-row"><div class="k">Animal</div><div class="v">{entry.get('animal', '')}</div></div>
    </div>
    <div class="col">
      <div class="summary-text">{entry.get('summary', '')}</div>
    </div>
    <div class="col link-col">
      <a class="link-btn" href="{entry.get('paper_url', '#')}" target="_blank" rel="noopener">Read paper</a>
      <a class="link-btn" href="{entry.get('github_url', '#')}" target="_blank" rel="noopener">GitHub</a>
      <button class="link-btn tutorial" onclick="openPopup({idx})">Tutorial</button>
    </div>
  </div>
</div>
<div class="overlay" id="overlay-{idx}">
  <div class="popup">
    <button class="popup-close" onclick="closePopup({idx})">✕</button>
    <div class="popup-title">{entry.get('title', '')} — tutorial</div>
    <div class="popup-text">{entry.get('tutorial', '(no tutorial generated)')}</div>
  </div>
</div>
"""


def generate_review_page(new_entries: list, run_date: str) -> Path:
    """Writes a self-contained HTML page with this run's new cards, so you
    can visually spot-check the AI-generated fields before trusting them."""
    REVIEWS_DIR.mkdir(exist_ok=True)
    output_path = REVIEWS_DIR / f"review-{run_date}.html"

    cards_html = "\n".join(_card_html(e, i) for i, e in enumerate(new_entries))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Review — {run_date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Stack+Sans+Text:wght@400;500;600&family=Fraunces:opsz,wght@9..144,500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{_REVIEW_CSS}</style>
</head>
<body>
<h1>Weekly review — {run_date}</h1>
<div class="sub">{len(new_entries)} new entr{'y' if len(new_entries) == 1 else 'ies'} added this run · all written to data/papers/ with verified: false until you check them</div>
{cards_html}
<script>
function openPopup(i){{ document.getElementById('overlay-' + i).classList.add('open'); }}
function closePopup(i){{ document.getElementById('overlay-' + i).classList.remove('open'); }}
document.querySelectorAll('.overlay').forEach(ov => {{
  ov.addEventListener('click', (e) => {{ if (e.target === ov) ov.classList.remove('open'); }});
}});
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="data/pending_papers.json", help="Path to the input queue")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds to wait between entries (be polite to APIs)")
    args = parser.parse_args()

    queue_path = REPO_ROOT / args.queue
    if not queue_path.exists():
        print(f"No queue file found at {queue_path}. Create it with a list of "
              f"{{paper_url, github_url}} pairs first.")
        sys.exit(1)

    queue = json.loads(queue_path.read_text())

    existing_urls = set()
    if PAPERS_DIR.exists():
        for f in PAPERS_DIR.glob("*.txt"):
            if f.name == "TEMPLATE.txt":
                continue
            try:
                existing_urls.add(build_index.parse_entry_file(f).get("paper_url"))
            except Exception:
                pass

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    added = 0
    new_entries = []
    for item in queue:
        paper_url = item.get("paper_url")
        github_url = item.get("github_url")
        access_status_override = item.get("access_status")  # optional, "open_access" | "paywall_restricted"
        if not paper_url or not github_url:
            continue
        if paper_url in existing_urls:
            print(f"Skipping (already indexed): {paper_url}")
            continue

        entry = process_entry(client, paper_url, github_url, access_status_override)
        if entry:
            filepath = write_entry_txt(entry)
            print(f"  Wrote {filepath}")
            new_entries.append(entry)
            added += 1
        time.sleep(args.delay)

    build_index.build()
    print(f"\nDone. Added {added} new entr{'y' if added == 1 else 'ies'} to {PAPERS_DIR}")

    if new_entries:
        review_path = generate_review_page(new_entries, date.today().isoformat())
        print(f"Review page written to {review_path} — open it in a browser to spot-check this week's entries.")
    print("Review new files in data/papers/ (verified: false) before flipping to true.")


if __name__ == "__main__":
    main()
