# scripts/

## add_publications.py

Adds new journal articles (and abstracts) to both the website (`data/publications.json`)
and the CV (`assets/cv/wmg_vita.tex`), then rebuilds the CV PDF.

### Monthly workflow

1. In Zotero, save the new journal articles to a collection.
2. Tag each item with:
   - `featured` — to surface it on the homepage selected-pubs grid
   - `gbd` or `nhlbi` — to associate it with the corresponding project filter
3. Export the collection as BibTeX:
   - File → Export Library… (or right-click the collection → Export Collection…)
   - Format: BibTeX. Save as `new_pubs.bib` in a fresh drop folder under `~/Downloads/`.
   - (Better BibTeX cite keys like `gardner_pipe_2026` work without modification.)
4. In the same folder, drop:
   - `<cite-key>.pdf` per article (the published or accepted PDF)
   - `<cite-key>.jpg` (or `.png`) per article (a thumbnail for the homepage card)

   Cite keys may use underscores or hyphens; both are matched.

5. Run:

   ```bash
   python3 scripts/add_publications.py ~/Downloads/website-update-2026-05
   ```

   The script:
   - parses the .bib file
   - copies PDFs and thumbnails into `uploads/publications/<id>/`
   - inserts JSON records in chronological order into `data/publications.json`
   - inserts `\ind` LaTeX lines below the `% [AUTO-INSERT: PUBLICATIONS]` marker
     in `assets/cv/wmg_vita.tex`
   - compiles the CV with `xelatex` (two passes) and copies the PDF to
     `uploads/wmg_vita.pdf`
   - cleans LaTeX build artifacts

   Nothing is committed. Run `git status` / `git diff` to review.

### Flags

```
--dry-run     Parse the .bib and print the generated JSON + LaTeX; touch no files.
--no-build    Update the .tex and .json but skip the xelatex compilation step.
```

### Drop folder layout

```
~/Downloads/website-update-YYYY-MM/
├── new_pubs.bib
├── gardner-example-2026.pdf
├── gardner-example-2026.jpg
├── collab-something-2026.pdf
└── collab-something-2026.jpg
```

The metadata file may be named `new_pubs.bib` or any unique `*.bib` in the folder.

### Author parsing

BibTeX `author = {Gardner, William M and Balte, Pallavi P and ...}` is converted
to the site's `FM Surname` initial format (`WM Gardner`, `PP Balte`). Entries
with a single author whose name contains *Collaborators*, *Collaboration*,
*Group*, *Consortium*, or *Initiative* are treated as corporate authors and
rendered in the CV as `<Corporate> \emph{(including \textbf{Gardner WM}).}`.

### Manual touch-ups after running

- Homepage selected-publications cards in `index.html` are hand-curated — if a
  new pub gets `featured: true` and you want it on the homepage, add the card
  to `index.html` separately.
- The script's auto-link is just `[{label: "Article", url: ...}]`. Add
  infographic, code, or data links manually as needed.

### Dependencies

- Python 3.10+ with `bibtexparser` (1.4.x): `pip install bibtexparser`
- `xelatex` available on `PATH` (TeX Live / MacTeX), with Minion Pro and
  Unit-Medium fonts installed (the CV uses these).
