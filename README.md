# NeuroCodeForager

A searchable, hand-curated index of open-source tools cited in neuroscience
papers — pulled from "code availability" statements, categorized, and paired
with a short usage tutorial.

Static site, no backend. The site itself has no build step — it's plain
HTML/CSS/JS that fetches `data/entries.json` at runtime. That one JSON file
is *generated*, though: the real source of truth is `data/papers/`, a folder
of plain-text files, one per entry.


## "My toolkit" (save for later)

Every card has a "Save" button. Saved entries are stored in the visitor's
own browser (`localStorage`) — no account, no server, and not shared
between devices. `toolkit.html` lists whatever's saved on that device.
