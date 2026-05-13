document.addEventListener('DOMContentLoaded', () => {
  // Mobile nav toggle
  const toggle = document.querySelector('.nav-toggle');
  const navLinks = document.querySelector('.nav-links');
  if (toggle && navLinks) {
    toggle.addEventListener('click', () => {
      navLinks.classList.toggle('open');
      const expanded = navLinks.classList.contains('open');
      toggle.setAttribute('aria-expanded', expanded);
    });
    document.addEventListener('click', (e) => {
      if (!toggle.contains(e.target) && !navLinks.contains(e.target)) {
        navLinks.classList.remove('open');
        toggle.setAttribute('aria-expanded', false);
      }
    });
  }

  // Active nav link
  const currentPath = window.location.pathname.replace(/\/$/, '') || '/index.html';
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href').replace(/\/$/, '');
    if (
      (href === 'index.html' && (currentPath === '' || currentPath.endsWith('index.html'))) ||
      (href !== 'index.html' && href !== '#' && currentPath.endsWith(href))
    ) {
      a.classList.add('active');
    }
  });
});
