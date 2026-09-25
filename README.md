# NeuroCodeForager

A searchable, hand-curated index of open-source tools cited in neuroscience
papers — pulled from "code availability" statements, categorized, and paired
with a short usage tutorial.

Static site, no backend. The site itself has no build step — it's plain
HTML/CSS/JS that fetches `data/entries.json` at runtime. That one JSON file
is *generated*, though: the real source of truth is `data/papers/`, a folder
of plain-text files, one per entry.

## Structure

```
index.html          homepage: search + last indexed papers + suggest-a-paper + categories
category.html         one category's entries (?cat=<slug>)
detail.html            full page for one entry (?id=<entry id>) — click any card title
about.html             about page
toolkit.html            "My toolkit" — locally saved entries (see below)
assets/
  style.css             all styles (design tokens at the top)
  categories.js          <- single source of truth for the 8 categories
  icons.js                inline SVG icon set
  layout.js               injects the shared nav + footer into every page
  app.js                  data loading, search (Fuse.js), card rendering,
                          save/toolkit, cite (BibTeX)
data/
  papers/                 <- SOURCE OF TRUTH: one plain-text file per entry
    TEMPLATE.txt          copy this to start a new entry
  entries.json            GENERATED — compiled from data/papers/, don't hand-edit
  pending_papers.json     input queue for the automated pipeline
scripts/
  build_index.py          compiles data/papers/*.txt -> data/entries.json
  add_entry.py             interactive CLI: writes a new data/papers/*.txt, then builds
  index_papers.py           automated weekly pipeline: same, but AI-classified
  requirements.txt
```

## The plain-text database (`data/papers/`)

Each entry is one `.txt` file, in a simple `key: value` format — see
`data/papers/TEMPLATE.txt`. To add one by hand:

1. Copy `TEMPLATE.txt` to a new file, e.g. `2026-09-24-my-tool.txt`
   (date-prefixed filenames keep them sorted; the filename becomes the
   entry's id, so keep it unique).
2. Fill in the fields. `summary:` and `tutorial:` can span multiple lines —
   just keep typing until the next field.
3. Commit/push it (or drop it in through the GitHub web UI — Add file →
   Create new file, right inside `data/papers/`).

You never have to touch `data/entries.json` yourself. Any push that touches
`data/papers/**` triggers `.github/workflows/rebuild-index.yml`, which runs
`build_index.py` and commits the regenerated `entries.json` automatically.
If you're working locally and want to see the result before pushing, run:

```
cd scripts
python build_index.py
```

### Optional rich fields (for the full detail page)

Beyond the core fields, `TEMPLATE.txt` documents extra optional ones that
power the full per-entry page (`detail.html?id=...`, opened when someone
clicks a card title):

- `website_url` — a docs/project site button, separate from the main repo
- `extra_links:` — one `Label | URL` per line, for additional repos (e.g.
  a separate data-pipeline or pose-tracking repo)
- `abstract_long:` — a longer description for the "Paper" section (falls
  back to `summary` if left blank)
- `tutorial_intro:` / `tutorial_steps:` / `tutorial_output:` — a structured,
  numbered-steps tutorial (used instead of the flat `tutorial:` field if
  present)
- `sample_data_text` / `sample_data_url` — a "Get sample data" box
- `subjects_count` / `subjects_strains` / `subjects_notes` — extra animal/
  subject details shown in the Details grid
- `related_ids:` — comma-separated ids (filenames without `.txt`) of other
  entries to show under "Related tools"

All of these are optional — the detail page just skips a section if there's
nothing to show. See `data/papers/2026-03-02-jabs.txt` for a fully-populated
example.

## Preview locally

Any static server works, e.g.:

```
python -m http.server 8000
```

then open `http://localhost:8000`. (Opening `index.html` directly via
`file://` will NOT work — `fetch()` of `data/entries.json` requires an
actual HTTP server, even a local one. VS Code's "Live Server" extension
works too — right-click `index.html` → "Open with Live Server".)

## Deploy to GitHub Pages

1. Push this repo to GitHub.
2. Settings → Pages → Source → Deploy from branch → `main`, folder `/ (root)`.
3. Your site will be live at `https://<username>.github.io/<repo-name>/`
   (or your custom domain, if you've set one up with a `CNAME`).

## Adding entries

### Option A — by hand, via the CLI (`add_entry.py`)
```
cd scripts
pip install -r requirements.txt --break-system-packages
python add_entry.py
```
Walks you through the fields, writes a new file into `data/papers/`, and
rebuilds `entries.json` for you.

### Option B — by hand, no script at all
Copy `data/papers/TEMPLATE.txt`, fill it in, commit. The GitHub Action
rebuilds the site's data automatically (see above).

### Option C — automated weekly batch (`index_papers.py`)
The pipeline meant to run unattended (locally on a schedule, or via
`.github/workflows/weekly-index.yml`).

It expects a **queue** of already-discovered `{paper_url, github_url}` pairs
at `data/pending_papers.json` — finding those pairs (crawling journals for
code-availability links) is a separate, future script; this one only
**enriches and indexes** pairs you already have.

For each pair, it automatically:
1. Determines **open access status** — either taken directly from an
   optional `"access_status"` field you set in the queue (since you'll
   already know this per journal/source you're pulling from), or guessed
   from the domain if you don't set one. Binary: `open_access` /
   `paywall_restricted`.
2. Looks up **citation count** via the Semantic Scholar API.
3. Looks up **title, authors, journal, year** via the Crossref API (from the
   DOI) — far more reliable than scraping for author lists, and what powers
   the "Cite" (BibTeX) button on each card.
4. Fetches the **GitHub README + detected language**.
5. Calls **Claude** (Anthropic API) with the abstract + README as context to
   generate: category, tags, a short summary, the specific data acquisition
   method (with brand/model when identifiable), animal (if applicable),
   difficulty, and a step-by-step tutorial. When a paper is paywalled,
   Claude is explicitly told to lean on the repo/README and the abstract
   only, rather than assuming full-text access.
6. Writes the result into `data/papers/` as a plain-text file with
   `verified: false`, then rebuilds `entries.json`.

Setup:
```
cd scripts
pip install -r requirements.txt --break-system-packages
export ANTHROPIC_API_KEY=...
python index_papers.py --queue data/pending_papers.json
```

Each run also writes `reviews/review-YYYY-MM-DD.html` — a self-contained
page with that run's new cards, so you can spot-check the AI-generated
fields visually before trusting them. Open it in a browser.

**Running it weekly without your computer on:** the included
`.github/workflows/weekly-index.yml` runs this automatically every Monday.
You just need to add one repo secret (Settings → Secrets and variables →
Actions): `ANTHROPIC_API_KEY`. It commits the new `data/papers/*.txt` files,
the rebuilt `entries.json`, and the review page straight back to the repo.

Note: `ANTHROPIC_API_KEY` requires an API account at console.anthropic.com
with billing set up — this is separate from a claude.ai subscription.

## "My toolkit" (save for later)

Every card has a "Save" button. Saved entries are stored in the visitor's
own browser (`localStorage`) — no account, no server, and not shared
between devices. `toolkit.html` lists whatever's saved on that device.

## Editing categories

Edit `assets/categories.js`. Every page (nav dropdown, homepage grid,
category page headers) reads from that one list, so you only need to
change it in one place. Keep the `category:` value in each `data/papers/*.txt`
file matching a `slug` from that list exactly.
