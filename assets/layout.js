function renderLayout(){
  const navHost = document.getElementById('site-nav');
  const footerHost = document.getElementById('site-footer');

  if (navHost){
    const items = CATEGORIES.map(c =>
      `<a href="category.html?cat=${c.slug}"><span class="dot"></span>${c.name}</a>`
    ).join('');

    navHost.innerHTML = `
      <div class="nav-left">
        <a href="index.html" style="display:flex; align-items:center; gap:11px;">
          <span class="logo-mark">${ICONS.logoMark()}</span>
          <span class="logo-word">neurocode<span class="accent">forager</span></span>
        </a>
      </div>
      <div class="nav-right">
        <div class="dropdown">
          <span>Browse by category</span>
          <div class="dropdown-menu"><div class="dropdown-menu-inner">${items}</div></div>
        </div>
        <a href="about.html">About</a>
        <button class="nav-toolkit" onclick="location.href='toolkit.html'">
          ${ICONS.bookmark}
          My toolkit <span class="count" id="toolkitCount">0</span>
        </button>
      </div>`;
    if (typeof updateToolkitCount === 'function') updateToolkitCount();
  }

  if (footerHost){
    footerHost.innerHTML = `
      <span class="logo-word">neurocode<span class="accent">forager</span></span>
      <div class="footer-links">
        <a href="https://github.com/paulagsotres/neurocodeforager" target="_blank" rel="noopener">GitHub</a>
        <a href="https://www.linkedin.com/in/paula-g%C3%B3mez-sotres-722242151/" target="_blank" rel="noopener">LinkedIn</a>
        <a href="mailto:neurocodeforager@gmail.com">Contact</a>
      </div>`;
  }
}

document.addEventListener('DOMContentLoaded', renderLayout);
