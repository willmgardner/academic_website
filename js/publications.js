/* Renders and filters the full publications list on publications.html */

const ME_PATTERNS = ['WM Gardner', 'William Gardner'];
const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function formatVenue(pub) {
  const monthLabel = (pub.month >= 1 && pub.month <= 12) ? `${MONTHS_SHORT[pub.month - 1]} ${pub.year}` : `${pub.year}`;
  return `<span class="journal-name">${pub.journal}</span> · ${monthLabel}`;
}

function isMe(author) {
  return ME_PATTERNS.some(p => author.includes(p));
}

function renderAuthor(author, coFirstSet) {
  const dagger = coFirstSet.has(author) ? '<sup class="author-dagger">&dagger;</sup>' : '';
  const inner = isMe(author) ? `<span class="author-me">${author}</span>` : author;
  return `${inner}${dagger}`;
}

function formatAuthors(pub, expanded) {
  const authors = pub.authors;
  const coFirstSet = new Set(pub.coFirstAuthors || []);
  const THRESHOLD = 6;
  if (authors.length <= THRESHOLD || expanded) {
    return authors.map(a => renderAuthor(a, coFirstSet)).join(', ');
  }
  // Show first 3 + toggle
  const visible = authors.slice(0, 3).map(a => renderAuthor(a, coFirstSet)).join(', ');
  return `<span class="authors-short">${visible}, </span>
          <span class="authors-full"></span>
          <button class="authors-toggle" aria-label="Show all authors">et al. [+${authors.length - 3}]</button>`;
}

function buildLink(href, label) {
  return `<a href="${href}" target="_blank" rel="noopener" class="link-btn">${label}</a>`;
}

function renderEntry(pub) {
  const titleHref = pub.doi
    ? `https://doi.org/${pub.doi}`
    : (pub.url || null);

  const titleEl = titleHref
    ? `<a href="${titleHref}" target="_blank" rel="noopener">${pub.title}</a>`
    : pub.title;

  const typeBadge = pub.type === 'abstract'
    ? '<span class="type-badge type-badge--abstract">Conference abstract</span>'
    : '';

  const authorHtml = formatAuthors(pub, false);

  const venueEl = formatVenue(pub);

  const pdfLink = pub.pdf ? buildLink(pub.pdf, 'PDF') : '';
  const doiLink = pub.doi
    ? buildLink(`https://doi.org/${pub.doi}`, 'DOI')
    : (pub.url ? buildLink(pub.url, 'Article') : '');
  const extraLinks = pub.links.map(l => buildLink(l.url, l.label)).join('');

  const imageHtml = pub.image
    ? `<div class="pub-entry-thumb">
         <img src="${pub.image}" alt="Figure from ${pub.title}" loading="lazy">
       </div>`
    : '';

  const hasImage = pub.image ? ' pub-entry--with-image' : '';

  return `
    <div class="pub-entry${hasImage}" data-projects="${pub.projects.join(' ')}" data-year="${pub.year}" data-type="${pub.type || 'article'}" data-id="${pub.id}">
      ${imageHtml}
      <div class="pub-entry-body">
        <div class="pub-entry-header">
          <div class="pub-entry-title">${titleEl}</div>
        </div>
        <div class="pub-entry-authors">${authorHtml}</div>
        <div class="pub-entry-venue">${venueEl} ${typeBadge}</div>
        <div class="pub-entry-links">${pdfLink}${doiLink}${extraLinks}</div>
      </div>
    </div>`;
}

function groupByYear(pubs) {
  const groups = {};
  pubs.forEach(p => {
    if (!groups[p.year]) groups[p.year] = [];
    groups[p.year].push(p);
  });
  Object.values(groups).forEach(arr => arr.sort((a, b) => (b.month || 0) - (a.month || 0)));
  return groups;
}

function renderList(pubs, container) {
  if (pubs.length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted);padding:32px 0">No publications match this filter.</p>';
    return;
  }

  const groups = groupByYear(pubs);
  const years = Object.keys(groups).map(Number).sort((a, b) => b - a);

  container.innerHTML = years.map(year => `
    <div class="pub-year-group">
      <div class="pub-year-label">${year}</div>
      <div class="pub-list">
        ${groups[year].map(renderEntry).join('')}
      </div>
    </div>`).join('');

  // Wire up author expand/collapse
  container.querySelectorAll('.authors-toggle').forEach(btn => {
    const entry = btn.closest('[data-id]');
    const id = entry.dataset.id;
    const pub = window.__pubs.find(p => p.id === id);
    const coFirstSet = new Set(pub.coFirstAuthors || []);
    btn.addEventListener('click', () => {
      const full = btn.previousElementSibling;
      const isExpanded = full.classList.contains('expanded');
      if (isExpanded) {
        full.classList.remove('expanded');
        full.innerHTML = '';
        btn.textContent = `et al. [+${pub.authors.length - 3}]`;
      } else {
        full.classList.add('expanded');
        full.innerHTML = pub.authors.slice(3).map(a => renderAuthor(a, coFirstSet)).join(', ');
        btn.textContent = 'collapse';
      }
    });
  });
}

function updateCount(n, total) {
  const el = document.querySelector('.filter-count');
  if (el) el.textContent = n === total ? `${total} publications` : `${n} of ${total} publications`;
}

document.addEventListener('DOMContentLoaded', async () => {
  const container = document.getElementById('pub-list-container');
  if (!container) return;

  container.classList.add('loading');

  let data;
  try {
    const res = await fetch('data/publications.json');
    data = await res.json();
  } catch (e) {
    container.classList.remove('loading');
    container.innerHTML = '<p style="color:var(--text-muted)">Could not load publications. Please open this page via a local server (e.g. <code>python3 -m http.server</code>).</p>';
    return;
  }

  container.classList.remove('loading');
  window.__pubs = data.publications;

  const filters = { project: 'all', type: 'all' };

  function applyFilters() {
    let filtered = window.__pubs;
    if (filters.project !== 'all') {
      filtered = filtered.filter(p => p.projects.includes(filters.project));
    }
    if (filters.type !== 'all') {
      filtered = filtered.filter(p => (p.type || 'article') === filters.type);
    }
    renderList(filtered, container);
    updateCount(filtered.length, window.__pubs.length);
  }

  applyFilters();

  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.dataset.filterGroup;
      document.querySelectorAll(`.filter-btn[data-filter-group="${group}"]`)
        .forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filters[group] = btn.dataset.filter;
      applyFilters();
    });
  });
});
