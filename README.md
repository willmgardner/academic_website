# willgardner.io

Personal academic website for William Gardner, MD MPH. Static HTML/CSS/JS, no build step.

## Stack

- Plain HTML/CSS/JS
- Publications rendered at page load from `data/publications.json`
- Deployed via Netlify, custom domain `willgardner.io`

## Local development

Run a local server (required for `fetch()` to load JSON):

```
python3 -m http.server 8080
```

Open http://localhost:8080.

## Adding a publication

1. Add an object to `data/publications.json`.
2. (Optional) Drop the featured image at `uploads/publications/<id>/featured.jpg` and the PDF at `uploads/publications/<id>/<id>.pdf`.
3. Commit and push to `main`. Netlify auto-deploys.

## Repo structure

- `index.html`, `publications.html`, `research.html`, `writing.html` — pages
- `css/style.css` — design system and all page styles
- `js/main.js`, `js/publications.js` — shared behavior and the publications renderer
- `data/publications.json` — publication data
- `uploads/` — PDFs and per-publication assets
- `assets/` — site-wide images (favicon, portrait, research banners)
- `netlify.toml` — deploy config and 301 redirects from old Hugo paths

## Previous version

The previous Hugo Academic (Wowchemy) version of this site is preserved on the `hugo-archive` branch and tagged `v-hugo-final`.
