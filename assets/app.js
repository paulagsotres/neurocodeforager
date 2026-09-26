let ENTRIES_CACHE = null;
let POPUP_COUNTER = 0;

async function loadEntries(){
  if (ENTRIES_CACHE) return ENTRIES_CACHE;
  let res;
  try {
    res = await fetch('data/entries.json');
  } catch (err) {
    throw new Error(
      "Couldn't load data/entries.json. If you opened this file directly " +
      "(file://...), that won't work — fetch() requires a real HTTP server. " +
      "Serve this folder with 'python -m http.server' or VS Code's Live Server, " +
      "then open it via http://localhost..."
    );
  }
  if (!res.ok){
    throw new Error(`data/entries.json returned ${res.status} — check the file exists at that path.`);
  }
  ENTRIES_CACHE = await res.json();
  return ENTRIES_CACHE;
}

// Shared tutorial renderer: structured (intro/steps/output) if present,
// else the older flat "tutorial" field, else an empty-state note.
function buildTutorialHTML(entry){
  if (entry.tutorial_intro || (entry.tutorial_steps && entry.tutorial_steps.length) || entry.tutorial_output){
    const stepsHTML = (entry.tutorial_steps || []).map(s => `<li>${s}</li>`).join('');
    return `
      ${entry.tutorial_intro ? `<p><strong>Input data:</strong> ${entry.tutorial_intro.replace(/^Input data:\s*/i, '')}</p>` : ''}
      ${stepsHTML ? `<ol>${stepsHTML}</ol>` : ''}
      ${entry.tutorial_output ? `<p><strong>What you get out:</strong> ${entry.tutorial_output}</p>` : ''}`;
  } else if (entry.tutorial) {
    return `<p style="white-space:pre-wrap;">${entry.tutorial}</p>`;
  }
  return `<p class="empty-note">No tutorial written yet for this entry.</p>`;
}

// ---------- Card + tutorial popup ----------
// Each card gets a unique popup id so several cards can be on the page at once
// (e.g. the "last indexed" list) without their popups colliding.
function cardHTML(entry){
  const cats = getEntryCategories(entry).map(getCategory).filter(Boolean);
  const popupId = 'popup-' + (POPUP_COUNTER++);

  const catPills = cats.map(c => `<span class="tag cat">${c.name}</span>`).join('');
  const authors = entry.authors || '';
  const dateLabel = entry.date || entry.year || '';

  const cardMarkup = `
    <div class="card" data-id="${entry.id}" data-authors="${authors.replace(/"/g, '&quot;')}" data-journal="${entry.journal || ''}" data-year="${entry.year || ''}" data-doi="${entry.doi || ''}">
      <div class="card-head">
        <div class="card-head-main">
          <a class="card-title" href="detail.html?id=${encodeURIComponent(entry.id)}">${entry.title}</a>
          <div class="tag-row">
            ${catPills}
            ${entry.journal ? `<span class="tag journal">${entry.journal}</span>` : ''}
            ${dateLabel ? `<span class="tag plain">${dateLabel}</span>` : ''}
          </div>
        </div>
        <button class="save-btn" onclick="toggleSave(this)">
          ${ICONS.bookmark}<span> Save</span>
        </button>
      </div>
      <div class="card-body">
        <div class="col">
          <div class="meta-row"><div class="k">Data acquisition</div><div class="v">${entry.data_acquisition || 'Not specified'}</div></div>
          <div class="meta-row"><div class="k">Language</div><div class="v">${entry.language || '—'}</div></div>
          <div class="meta-row"><div class="k">Animal</div><div class="v">${entry.animal || 'Not applicable'}</div></div>
        </div>
        <div class="col">
          <div class="summary-text">${entry.summary || ''}</div>
        </div>
        <div class="col link-col">
          <a class="link-btn" href="${entry.paper_url || '#'}" target="_blank" rel="noopener">
            ${ICONS.paper} Read paper
          </a>
          <a class="link-btn" href="${(entry.code && entry.code.repo_url) || '#'}" target="_blank" rel="noopener">
            ${ICONS.github} GitHub
          </a>
          <button class="link-btn tutorial" onclick="openPopup('${popupId}')">
            ${ICONS.tutorial} Tutorial
          </button>
          <button class="link-btn" onclick="showCite(this, event)">
            ${ICONS.cite} Cite
          </button>
        </div>
      </div>
    </div>`;

  const popupMarkup = `
    <div class="overlay" id="${popupId}">
      <div class="popup">
        <button class="popup-close" onclick="closePopup('${popupId}')">✕</button>
        <div class="popup-title">${entry.title}</div>
        <div class="popup-subtitle">mini tutorial</div>
        <div class="popup-text">${buildTutorialHTML(entry)}</div>
      </div>
    </div>`;

  return { cardMarkup, popupMarkup };
}

function renderCards(container, entries){
  const cards = [];
  const popups = [];
  entries.forEach(e => {
    const { cardMarkup, popupMarkup } = cardHTML(e);
    cards.push(cardMarkup);
    popups.push(popupMarkup);
  });
  container.innerHTML = cards.join('') + popups.join('');
  applySavedState();
}

/* ---------- favorites ("My toolkit"): localStorage, no account needed ---------- */
const TOOLKIT_STORAGE_KEY = 'ncf_saved_tools';

function getSavedIds(){
  try { return JSON.parse(localStorage.getItem(TOOLKIT_STORAGE_KEY)) || []; }
  catch(e){ return []; }
}
function setSavedIds(arr){
  localStorage.setItem(TOOLKIT_STORAGE_KEY, JSON.stringify(arr));
  updateToolkitCount();
}
function updateToolkitCount(){
  const el = document.getElementById('toolkitCount');
  if (el) el.textContent = getSavedIds().length;
}
function applySavedState(){
  const saved = getSavedIds();
  document.querySelectorAll('[data-id]').forEach(card => {
    const id = card.dataset.id;
    const btn = card.querySelector('.save-btn');
    if (!btn) return;
    const isSaved = saved.includes(id);
    btn.classList.toggle('saved', isSaved);
    btn.querySelector('span').textContent = isSaved ? ' Saved' : ' Save';
  });
  updateToolkitCount();
}
function toggleSave(btn){
  const card = btn.closest('[data-id]');
  const id = card.dataset.id;
  let saved = getSavedIds();
  saved = saved.includes(id) ? saved.filter(x => x !== id) : [...saved, id];
  setSavedIds(saved);
  applySavedState();
}

/* ---------- cite (BibTeX) ---------- */
function ensureCitePop(){
  let pop = document.getElementById('citePop');
  if (!pop){
    pop = document.createElement('div');
    pop.className = 'cite-pop';
    pop.id = 'citePop';
    pop.innerHTML = `<pre id="citeText"></pre><button onclick="copyCite()">Copy BibTeX</button>`;
    document.body.appendChild(pop);
  }
  return pop;
}
function showCite(btn, evt){
  evt.stopPropagation();
  const card = btn.closest('[data-id]');
  const { id, authors, journal, year, doi } = card.dataset;
  const titleEl = card.querySelector('.card-title') || card.querySelector('h1');
  const title = titleEl ? titleEl.textContent.trim() : '';
  const bibtex = `@article{${id}${year},
  title   = {${title}},
  author  = {${authors}},
  journal = {${journal}},
  year    = {${year}},
  doi     = {${doi}}
}`;
  const pop = ensureCitePop();
  document.getElementById('citeText').textContent = bibtex;
  pop.dataset.cite = bibtex;
  const rect = btn.getBoundingClientRect();
  pop.style.top = (window.scrollY + rect.bottom + 8) + 'px';
  pop.style.left = Math.max(16, rect.left - 200) + 'px';
  pop.classList.add('show');
}
document.addEventListener('click', (ev) => {
  const pop = document.getElementById('citePop');
  if (pop && !ev.target.closest('.cite-pop') && !ev.target.closest('.link-btn')){
    pop.classList.remove('show');
  }
});
function copyCite(){
  const pop = document.getElementById('citePop');
  navigator.clipboard.writeText(pop.dataset.cite);
  const btn = pop.querySelector('button');
  const old = btn.textContent;
  btn.textContent = 'Copied ✓';
  setTimeout(() => btn.textContent = old, 1200);
}

// Simpler rectangular card, used for "Last indexed papers" on the homepage
function squareCardHTML(entry){
  const cats = getEntryCategories(entry).map(getCategory).filter(Boolean);
  const cat = cats[0];

  const cardMarkup = `
    <a class="square-card" href="detail.html?id=${encodeURIComponent(entry.id)}">
      <div>
        <div class="sq-cat">${(cat && cat.name) || ''}</div>
        <div class="sq-title">${entry.title}</div>
      </div>
      <div class="sq-lang">${entry.language || ''}</div>
    </a>`;

  return { cardMarkup, popupMarkup: '' };
}

function renderSquareCards(container, entries){
  const cards = entries.map(e => squareCardHTML(e).cardMarkup);
  container.innerHTML = `<div class="square-grid">${cards.join('')}</div>`;
}

function openPopup(id){ document.getElementById(id).classList.add('open'); }
function closePopup(id){ document.getElementById(id).classList.remove('open'); }
document.addEventListener('click', (e) => {
  if (e.target.classList && e.target.classList.contains('overlay')) {
    e.target.classList.remove('open');
  }
});

function faviconFor(url){
  try{
    const domain = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
  }catch(e){ return ''; }
}

function renderCategoryGrid(container, entries){
  container.innerHTML = CATEGORIES.map(c => {
    const count = entries.filter(e => getEntryCategories(e).includes(c.slug)).length;
    return `
      <a class="cat-card" href="category.html?cat=${c.slug}">
        <div class="icon">${ICONS[c.icon] || ''}</div>
        <h3>${c.name}</h3>
        <p>${c.desc}</p>
        <span class="count">${count} ${count === 1 ? 'entry' : 'entries'}</span>
      </a>`;
  }).join('');
}

// ---------- Homepage: search + last indexed + category grid ----------
async function initHome(){
  let entries;
  try {
    entries = await loadEntries();
  } catch (err) {
    const catsSection = document.getElementById('categories-section');
    const lastIndexedSection = document.getElementById('last-indexed-section');
    const errorHTML = `<div class="empty-state" style="color:#a6472a;">${err.message}</div>`;
    if (lastIndexedSection) lastIndexedSection.innerHTML = errorHTML;
    if (catsSection) catsSection.style.display = 'none';
    console.error(err);
    return;
  }

  const grid = document.getElementById('cat-grid');
  const catsSection = document.getElementById('categories-section');
  if (grid) renderCategoryGrid(grid, entries);

  const lastIndexedList = document.getElementById('last-indexed-list');
  const lastIndexedDate = document.getElementById('last-indexed-date');
  if (lastIndexedList){
    const sorted = [...entries].sort((a, b) => new Date(b.added_date) - new Date(a.added_date));
    renderSquareCards(lastIndexedList, sorted.slice(0, 6));
    if (lastIndexedDate && sorted.length){
      lastIndexedDate.textContent = `${entries.length} tools indexed · updated ${sorted[0].added_date}`;
    }
  }

  const input = document.getElementById('search-input');
  const resultsSection = document.getElementById('results');
  const resultsList = document.getElementById('results-list');
  const countLabel = document.getElementById('search-count');
  const lastIndexedSection = document.getElementById('last-indexed-section');
  const suggestSection = document.getElementById('suggest-section');

  // Quick-tags: pull every tag used across all indexed entries, dedupe,
  // and show 6 random ones — re-rolled fresh on every page load. Populated
  // before the Fuse.js setup below so it still works even if that CDN fails.
  const quickTagsEl = document.getElementById('quick-tags');
  if (quickTagsEl && input){
    const allTags = [...new Set(entries.flatMap(e => e.tags || []))];
    const shuffled = allTags.sort(() => Math.random() - 0.5);
    const picked = shuffled.slice(0, 6);
    quickTagsEl.innerHTML = picked.map(t => `<span>${t}</span>`).join('');
    quickTagsEl.querySelectorAll('span').forEach(tagEl => {
      tagEl.addEventListener('click', () => {
        input.value = tagEl.textContent;
        input.focus();
        runSearch(tagEl.textContent);
      });
    });
  }

  if (!input) return;

  const fuse = new Fuse(entries, {
    includeScore: true,
    threshold: 0.35,
    ignoreLocation: true,
    keys: [
      { name: 'title', weight: 0.3 },
      { name: 'tags', weight: 0.25 },
      { name: 'authors', weight: 0.15 },
      { name: 'summary', weight: 0.15 },
      { name: 'journal', weight: 0.1 },
      { name: 'data_acquisition', weight: 0.1 },
      { name: 'animal', weight: 0.05 },
      { name: 'language', weight: 0.05 },
      { name: 'tutorial', weight: 0.05 },
    ],
  });

  function runSearch(query){
    const isSearching = !!query.trim();
    resultsSection.style.display = isSearching ? '' : 'none';
    catsSection.style.display = isSearching ? 'none' : '';
    if (lastIndexedSection) lastIndexedSection.style.display = isSearching ? 'none' : '';
    if (suggestSection) suggestSection.style.display = isSearching ? 'none' : '';
    if (!isSearching){
      countLabel.textContent = '';
      return;
    }

    const hits = fuse.search(query).map(r => r.item);
    countLabel.textContent = `${hits.length} result${hits.length === 1 ? '' : 's'}`;
    if (hits.length){
      renderCards(resultsList, hits);
    } else {
      resultsList.innerHTML = `<div class="empty-state">No matches yet — try a different keyword, or browse by category below.</div>`;
      catsSection.style.display = '';
    }
  }

  input.addEventListener('input', (e) => runSearch(e.target.value));
}

// ---------- Detail page (full page for one entry) ----------
function computeRelatedEntries(entry, allEntries){
  const myCats = new Set(getEntryCategories(entry));
  const myTags = new Set((entry.tags || []).map(t => t.toLowerCase().trim()));
  const myAnimal = (entry.animal || '').toLowerCase();
  const animalIsSpecific = myAnimal && !myAnimal.startsWith('not applicable');

  const scored = allEntries
    .filter(e => e.id !== entry.id)
    .map(e => {
      const cats = getEntryCategories(e);
      const catOverlap = cats.filter(c => myCats.has(c)).length;
      const tags = (e.tags || []).map(t => t.toLowerCase().trim());
      const tagOverlap = tags.filter(t => myTags.has(t)).length;
      const animal = (e.animal || '').toLowerCase();
      const sameAnimal = animalIsSpecific && animal.startsWith(myAnimal.split(/[,(]/)[0].trim()) ? 1 : 0;
      const score = catOverlap * 3 + tagOverlap * 1 + sameAnimal * 2;
      return { e, score };
    })
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .map(x => x.e);

  return scored;
}

async function initDetailPage(){
  const params = new URLSearchParams(window.location.search);
  const id = params.get('id');
  const main = document.getElementById('detail-main');
  let entries;
  try {
    entries = await loadEntries();
  } catch (err) {
    main.innerHTML = `<div class="empty-state" style="color:#a6472a;">${err.message}</div>`;
    console.error(err);
    return;
  }
  const entry = entries.find(e => e.id === id);

  if (!entry){
    main.innerHTML = `
      <a class="back-link" href="index.html">${ICONS.back} Back to search</a>
      <h1>Entry not found</h1>
      <p>Check the link, or <a href="index.html">go back home</a>.</p>`;
    return;
  }

  main.dataset.id = entry.id;
  main.dataset.authors = entry.authors || '';
  main.dataset.journal = entry.journal || '';
  main.dataset.year = entry.year || '';
  main.dataset.doi = entry.doi || '';
  document.title = `${entry.title} — NeuroCodeForager`;

  const cats = getEntryCategories(entry).map(getCategory).filter(Boolean);
  const accessTag = entry.access_status === 'open_access'
    ? '<span class="tag oa">open access</span>'
    : '<span class="tag paywall">paywall restricted</span>';
  const dateLabel = entry.date || entry.year || '';

  // Actions row: Save, Cite, main GitHub, any extra_links, website/docs, primary Read paper
  const extraLinkButtons = (entry.extra_links || []).map(l => `
    <a class="link-btn" href="${l.url}" target="_blank" rel="noopener">
      ${l.url.includes('github.com') ? ICONS.github : ICONS.globe} ${l.label}
    </a>`).join('');

  const websiteButton = entry.website_url ? `
    <a class="link-btn" href="${entry.website_url}" target="_blank" rel="noopener">
      ${ICONS.globe} Docs
    </a>` : '';

  const githubButton = (entry.code && entry.code.repo_url) ? `
    <a class="link-btn" href="${entry.code.repo_url}" target="_blank" rel="noopener">
      ${ICONS.github} GitHub
    </a>` : '';

  // Details info grid — only show rows that actually have something to say
  const infoRows = [
    ['Data acquisition', entry.data_acquisition],
    ['Animal', entry.animal],
    ['Language', entry.language],
    ['GPU required', entry.gpu_required ? (entry.gpu_required === 'yes' ? 'Yes' : 'No') : ''],
    ['DOI', entry.doi],
    ['Subjects', entry.subjects && entry.subjects.count ? [entry.subjects.count, entry.subjects.notes].filter(Boolean).join(' — ') : ''],
    ['Strain coverage', entry.subjects && entry.subjects.strains],
  ].filter(([, v]) => v);

  const infoGridHTML = infoRows.map(([k, v]) => `
    <div class="info-item"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');

  // Tutorial: structured (intro/steps/output) if present, else fall back to the flat field
  const tutorialHTML = buildTutorialHTML(entry);

  // Related tools — manually curated via related_ids if the entry sets it,
  // otherwise computed from shared categories/tags/animal with every other entry.
  const manualIds = entry.related_ids || [];
  const relatedEntries = manualIds.length
    ? manualIds.map(rid => entries.find(e => e.id === rid)).filter(Boolean)
    : computeRelatedEntries(entry, entries);
  const relatedHTML = relatedEntries.length
    ? `<div class="related-grid">${relatedEntries.map(r => `
        <a class="related-card" href="detail.html?id=${encodeURIComponent(r.id)}">
          <span class="rt">${r.title}</span>
          <span class="rm">${getEntryCategories(r).map(s => (getCategory(s) || {}).name).filter(Boolean).join(' · ')}</span>
        </a>`).join('')}</div>`
    : `<div class="empty-note">No related tools indexed yet.</div>`;

  main.innerHTML = `
    <a class="back-link" href="index.html">${ICONS.back} Back to search</a>

    <div class="detail-header">
      <h1>${entry.title}</h1>
      <div class="detail-authors">${entry.authors || ''}${entry.authors ? ' — ' : ''}${entry.journal || ''}${entry.year ? `, ${entry.year}` : ''}</div>
      <div class="tag-row">
        ${cats.map(c => `<span class="tag cat">${c.name}</span>`).join('')}
        ${accessTag}
        <span class="tag plain">${dateLabel}</span>
      </div>
    </div>

    <div class="detail-grid">
      <div class="detail-col-main">
        <section class="detail-section" style="border-top:none; padding-top:0;">
          <div class="section-label">Paper</div>
          <div class="paper-embed">
            <div class="thumb">${ICONS.paper}</div>
            <div>
              <b>${entry.title}</b>
              <span>${entry.journal || ''}${entry.year ? `, ${entry.year}` : ''} · ${entry.access_status === 'open_access' ? 'open access' : 'paywall restricted'}</span>
            </div>
            <a class="go" href="${entry.paper_url || '#'}" target="_blank" rel="noopener">View paper →</a>
          </div>
          ${(entry.abstract_long || entry.summary) ? `<div class="abstract-text">${entry.abstract_long || entry.summary}</div>` : ''}
        </section>

        <section class="detail-section">
          <div class="section-label">Tutorial</div>
          <div class="tutorial-text">${tutorialHTML}</div>
        </section>

        <section class="detail-section">
          <div class="section-label">Related tools</div>
          ${relatedHTML}
        </section>
      </div>

      <aside class="detail-col-side">
        <div class="actions">
          <button class="link-btn save" onclick="toggleSave(this)">${ICONS.bookmark}<span> Save</span></button>
          <button class="link-btn" onclick="showCite(this, event)">${ICONS.cite} Cite</button>
          ${githubButton}
          ${extraLinkButtons}
          ${websiteButton}
          <a class="link-btn primary" href="${entry.paper_url || '#'}" target="_blank" rel="noopener">${ICONS.paper} Read paper</a>
        </div>

        ${infoGridHTML ? `
        <section class="detail-section">
          <div class="section-label">Details</div>
          <div class="info-grid info-grid-side">${infoGridHTML}</div>
        </section>` : ''}

        ${(entry.sample_data && (entry.sample_data.text || entry.sample_data.url)) ? `
        <section class="detail-section">
          <div class="section-label">Sample data</div>
          <div class="sample-box">
            <div class="sd-text">${entry.sample_data.text || ''}</div>
            ${entry.sample_data.url ? `<a class="sd-btn" href="${entry.sample_data.url}" target="_blank" rel="noopener">Get sample data</a>` : ''}
          </div>
        </section>` : ''}
      </aside>
    </div>
  `;

  applySavedState();
}
async function initCategoryPage(){
  const params = new URLSearchParams(window.location.search);
  const slug = params.get('cat');
  const cat = getCategory(slug);
  let entries;
  try {
    entries = await loadEntries();
  } catch (err) {
    document.getElementById('cat-entries').innerHTML = `<div class="empty-state" style="color:#a6472a;">${err.message}</div>`;
    console.error(err);
    return;
  }

  const header = document.getElementById('cat-header');
  const list = document.getElementById('cat-entries');
  if (!cat){
    header.innerHTML = `<h1>Category not found</h1><p>Check the link or <a href="index.html">go back home</a>.</p>`;
    return;
  }

  header.innerHTML = `
    <a class="back" href="index.html">&larr; all categories</a>
    <div class="icon-lg">${ICONS[cat.icon] || ''}</div>
    <h1>${cat.name}</h1>
    <p>${cat.desc}</p>`;

  const filtered = entries.filter(e => getEntryCategories(e).includes(slug));
  if (filtered.length){
    renderCards(list, filtered);
  } else {
    list.innerHTML = `<div class="empty-state">No entries indexed in this category yet.</div>`;
  }
}
