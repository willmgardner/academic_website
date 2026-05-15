# willgardner.io

Source for [willgardner.io](https://willgardner.io), the personal academic website of William M. Gardner, MD MPH.

## Stack

- Static HTML, CSS, and JS — no build step or framework
- Publications and per-pub author data rendered at page load from JSON
- Deployed via Netlify

## Repo structure

- `index.html`, `publications.html`, `research.html`, `writing.html` — top-level pages
- `css/style.css` — design system and all page styles
- `js/` — small renderer scripts (mobile nav, publications list)
- `data/` — publication metadata and per-pub author lists
- `assets/` — site-wide images and the CV LaTeX source
- `uploads/` — PDFs and per-publication assets served at static URLs

## License

Content © William M. Gardner; site source code licensed [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
