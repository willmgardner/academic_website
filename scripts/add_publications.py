#!/usr/bin/env python3
"""
add_publications.py — add new journal articles to the website and CV.

Usage:
    python scripts/add_publications.py <drop_folder> [--no-build] [--dry-run]

The drop folder should contain:
    new_pubs.bib              # Zotero export (BibTeX). Any *.bib also works if unique.
    <cite-key>.pdf            # one per @article entry (optional)
    <cite-key>.{jpg,jpeg,png} # one thumbnail per @article entry (optional)

Cite keys may use either underscores (Zotero default) or hyphens — both are
matched against asset filenames; the website id is the kebab-case form.

Per-pub flags are read from each entry's `keywords` field (set as Zotero tags):
    featured     -> homepage selected-pubs grid
    gbd          -> projects: ["gbd"]
    nhlbi        -> projects: ["nhlbi"]

The script:
  1. Parses the .bib file
  2. Builds a publications.json record + LaTeX line for each entry
  3. Copies PDF + thumbnail into uploads/publications/<id>/
  4. Inserts JSON entries into data/publications.json in chronological order
  5. Inserts \\ind LaTeX lines below the AUTO-INSERT marker in assets/cv/wmg_vita.tex
  6. Compiles assets/cv/wmg_vita.tex via xelatex (twice); copies the PDF to uploads/wmg_vita.pdf
  7. Cleans LaTeX intermediates

Nothing is committed. Review the diff and commit manually.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode


REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLICATIONS_JSON = REPO_ROOT / "data" / "publications.json"
CV_TEX = REPO_ROOT / "assets" / "cv" / "wmg_vita.tex"
CV_PDF_OUT = REPO_ROOT / "uploads" / "wmg_vita.pdf"
UPLOADS_PUBS = REPO_ROOT / "uploads" / "publications"

AUTO_INSERT_MARKER = "% [AUTO-INSERT: PUBLICATIONS]"

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}

PROJECT_TAGS = {"gbd", "nhlbi"}
CORPORATE_KEYWORDS = ("collaborators", "collaboration", "group", "consortium", "initiative")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def kebab(key: str) -> str:
    return key.lower().replace("_", "-").strip()


def clean_text(text: str) -> str:
    """Strip BibTeX-preserved braces and collapse whitespace."""
    if not text:
        return ""
    t = re.sub(r"[{}]", "", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def latex_escape(text: str) -> str:
    """Escape LaTeX special characters in plain prose (titles, journal names)."""
    repl = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }
    return re.sub(r"[&%$#_~^\\]", lambda m: repl[m.group(0)], text)


# ---------------------------------------------------------------------------
# BibTeX field parsing
# ---------------------------------------------------------------------------

def parse_month(raw: str) -> int | None:
    if not raw:
        return None
    raw = raw.strip().strip("{}").lower()
    if raw.isdigit():
        n = int(raw)
        return n if 1 <= n <= 12 else None
    return MONTH_MAP.get(raw)


def initials(given: str) -> str:
    parts = re.split(r"[\s.\-]+", given.strip())
    return "".join(p[0].upper() for p in parts if p)


def parse_author(raw: str) -> str:
    """
    Convert a BibTeX author to the site's 'FM Surname' format.
        'Gardner, William M'         -> 'WM Gardner'
        'GBD 2023 Collaborators'     -> 'GBD 2023 Collaborators'  (corporate; no comma)
        '{GBD 2023 Collaborators}'   -> same (braces stripped)
    """
    name = raw.strip().strip("{}").strip()
    if "," not in name:
        return name
    last, given = name.split(",", 1)
    return f"{initials(given)} {last.strip()}"


def split_bib_authors(raw: str) -> list[str]:
    if not raw:
        return []
    return [a.strip() for a in re.split(r"\s+and\s+", raw.strip(), flags=re.IGNORECASE) if a.strip()]


def is_corporate(name: str) -> bool:
    return ("," not in name) and any(kw in name.lower() for kw in CORPORATE_KEYWORDS)


def gardner_position(authors: list[str]) -> int | None:
    """0-based index of WM Gardner in the author list, or None."""
    targets = {"WM Gardner", "William Gardner", "William M Gardner"}
    for i, a in enumerate(authors):
        if a in targets:
            return i
    return None


# ---------------------------------------------------------------------------
# LaTeX line construction
# ---------------------------------------------------------------------------

def render_authors_latex(authors: list[str], cap: int = 6) -> str:
    """
    Author block for a CV \\ind line.

    Returns text terminating in either '.' (full list) or '\\emph{et al.}' (truncated)
    or '\\emph{(including \\textbf{Gardner WM}).}' (corporate collaborator).
    """
    if len(authors) == 1 and is_corporate(authors[0]):
        return f"{latex_escape(authors[0])} \\emph{{(including \\textbf{{Gardner WM}}).}}"

    pos = gardner_position(authors)

    if pos is None:
        head = authors[:cap]
        body = ", ".join(latex_escape(a) for a in head)
        return body + (r", \emph{et al.}" if len(authors) > cap else ".")

    # Gardner in list: include enough authors to reach Gardner, with 1 author after when room allows.
    head_count = min(max(pos + 2, 4), cap)
    head_count = min(head_count, len(authors))
    parts = []
    for a in authors[:head_count]:
        if a == "WM Gardner":
            parts.append(r"{\minbold Gardner WM}")
        else:
            parts.append(latex_escape(a))
    body = ", ".join(parts)
    return body + (r", \emph{et al.}" if len(authors) > head_count else ".")


def build_latex_line(record: dict, volume: str | None, pages: str | None) -> str:
    authors = record["authors"]
    title = record["title"]
    journal = record["journal"]
    year = record["year"]
    doi = record.get("doi")

    author_block = render_authors_latex(authors)
    title_block = (
        rf"\href{{https://doi.org/{doi}}}{{{latex_escape(title)}}}"
        if doi else latex_escape(title)
    )

    locator = ""
    if volume and pages:
        locator = f"; {volume}: {pages}"
    elif volume:
        locator = f"; {volume}"
    elif pages:
        locator = f"; {pages}"

    venue_block = rf"\emph{{{latex_escape(journal)}}} {year}{locator}."
    return rf"\item {author_block} {title_block}. {venue_block}"


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------

def build_json_record(entry: dict) -> dict:
    citekey = entry["ID"]
    pub_id = kebab(citekey)
    authors = [parse_author(a) for a in split_bib_authors(entry.get("author", ""))]

    raw_keywords = entry.get("keywords", "")
    kw = {k.strip().lower() for k in re.split(r"[,;]\s*", raw_keywords) if k.strip()}
    featured = "featured" in kw
    projects = sorted(k for k in kw if k in PROJECT_TAGS)

    bib_type = entry.get("ENTRYTYPE", "article").lower()
    pub_type = "article" if bib_type == "article" else "abstract"

    doi = entry.get("doi") or None
    url = entry.get("url") or None
    if doi and not url:
        url = f"https://doi.org/{doi}"

    return {
        "id": pub_id,
        "title": clean_text(entry.get("title", "")),
        "authors": authors,
        "journal": clean_text(entry.get("journal", entry.get("booktitle", ""))),
        "year": int(entry.get("year", "0")),
        "month": parse_month(entry.get("month", "")),
        "doi": doi,
        "url": url,
        "featured": featured,
        "projects": projects,
        "image": None,
        "pdf": None,
        "links": [{"label": "Article", "url": url}] if url else [],
        "type": pub_type,
    }


# ---------------------------------------------------------------------------
# Asset copying
# ---------------------------------------------------------------------------

def find_asset(folder: Path, citekey: str, exts: tuple[str, ...]) -> Path | None:
    candidates = {citekey, kebab(citekey), citekey.replace("-", "_")}
    for name in candidates:
        for ext in exts:
            p = folder / f"{name}{ext}"
            if p.exists():
                return p
    return None


def copy_assets(record: dict, citekey: str, drop_folder: Path) -> None:
    pub_id = record["id"]
    target_dir = UPLOADS_PUBS / pub_id
    target_dir.mkdir(parents=True, exist_ok=True)

    pdf_src = find_asset(drop_folder, citekey, (".pdf",))
    if pdf_src:
        pdf_dst = target_dir / f"{pub_id}.pdf"
        shutil.copy2(pdf_src, pdf_dst)
        record["pdf"] = f"uploads/publications/{pub_id}/{pub_id}.pdf"

    img_src = find_asset(drop_folder, citekey, (".jpg", ".jpeg", ".png"))
    if img_src:
        ext = ".jpg" if img_src.suffix.lower() in (".jpg", ".jpeg") else ".png"
        img_dst = target_dir / f"featured{ext}"
        shutil.copy2(img_src, img_dst)
        record["image"] = f"uploads/publications/{pub_id}/featured{ext}"


# ---------------------------------------------------------------------------
# publications.json merging
# ---------------------------------------------------------------------------

def sort_key(p: dict) -> tuple[int, int]:
    return (-int(p.get("year", 0)), -(p.get("month") or 0))


def insert_into_publications(new_records: list[dict]) -> tuple[int, list[str]]:
    """Insert new records into publications.json, preserving existing ordering elsewhere.
    Returns (number added, list of skipped duplicate ids)."""
    data = json.loads(PUBLICATIONS_JSON.read_text())
    pubs = data["publications"]
    existing_ids = {p["id"] for p in pubs}

    added = 0
    skipped = []
    for rec in new_records:
        if rec["id"] in existing_ids:
            skipped.append(rec["id"])
            continue
        nk = sort_key(rec)
        inserted = False
        for i, p in enumerate(pubs):
            if nk < sort_key(p):
                pubs.insert(i, rec)
                inserted = True
                break
        if not inserted:
            pubs.append(rec)
        existing_ids.add(rec["id"])
        added += 1

    if added:
        PUBLICATIONS_JSON.write_text(
            json.dumps({"publications": pubs}, indent=2, ensure_ascii=False) + "\n"
        )
    return added, skipped


# ---------------------------------------------------------------------------
# CV LaTeX insertion
# ---------------------------------------------------------------------------

def insert_latex_entries(tex_lines: list[str]) -> None:
    content = CV_TEX.read_text()
    if AUTO_INSERT_MARKER not in content:
        raise SystemExit(
            f"AUTO-INSERT marker not found in {CV_TEX.relative_to(REPO_ROOT)}.\n"
            f"Ensure the line '{AUTO_INSERT_MARKER}' exists above the journal-article entries."
        )

    marker_pat = re.compile(
        re.escape(AUTO_INSERT_MARKER) + r".*?\n%.*?scripts/add_publications\.py.*?\n",
        re.DOTALL,
    )
    m = marker_pat.search(content)
    if m:
        insert_at = m.end()
    else:
        idx = content.index(AUTO_INSERT_MARKER)
        insert_at = content.index("\n", idx) + 1

    block = "\n" + "\n\n".join(tex_lines) + "\n"
    new_content = content[:insert_at] + block + content[insert_at:]
    CV_TEX.write_text(new_content)


# ---------------------------------------------------------------------------
# PDF build
# ---------------------------------------------------------------------------

def compile_pdf() -> bool:
    cv_dir = CV_TEX.parent
    print(f"\nCompiling {CV_TEX.relative_to(REPO_ROOT)} with xelatex...")
    for i in range(2):
        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", CV_TEX.name],
            cwd=cv_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  xelatex failed on pass {i + 1} (exit {result.returncode}).", file=sys.stderr)
            print("  --- last 30 lines of xelatex output ---", file=sys.stderr)
            tail = (result.stdout + result.stderr).splitlines()[-30:]
            for line in tail:
                print(f"    {line}", file=sys.stderr)
            _clean_latex_intermediates(cv_dir)
            return False

    built = cv_dir / "wmg_vita.pdf"
    if not built.exists():
        print("  xelatex completed but no PDF was produced.", file=sys.stderr)
        _clean_latex_intermediates(cv_dir)
        return False

    CV_PDF_OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, CV_PDF_OUT)
    print(f"  wrote {CV_PDF_OUT.relative_to(REPO_ROOT)}")
    _clean_latex_intermediates(cv_dir, also_pdf=True)
    return True


def _clean_latex_intermediates(cv_dir: Path, also_pdf: bool = False) -> None:
    suffixes = (".aux", ".log", ".out", ".toc", ".synctex.gz", ".fdb_latexmk", ".fls", ".bcf", ".run.xml")
    if also_pdf:
        suffixes = suffixes + (".pdf",)
    for ext in suffixes:
        for f in cv_dir.glob(f"*{ext}"):
            try:
                f.unlink()
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_bib(drop: Path) -> Path:
    bib = drop / "new_pubs.bib"
    if bib.exists():
        return bib
    bibs = list(drop.glob("*.bib"))
    if len(bibs) == 1:
        return bibs[0]
    if len(bibs) > 1:
        raise SystemExit(f"Multiple .bib files in {drop}; rename one to new_pubs.bib.")
    raise SystemExit(f"No .bib file found in {drop}.")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("drop_folder", type=Path, help="Folder containing new_pubs.bib and assets")
    ap.add_argument("--no-build", action="store_true", help="Skip xelatex compilation")
    ap.add_argument("--dry-run", action="store_true", help="Parse and print summary; do not write files")
    args = ap.parse_args()

    drop = args.drop_folder.expanduser().resolve()
    if not drop.is_dir():
        print(f"Drop folder does not exist: {drop}", file=sys.stderr)
        return 1

    bib_file = find_bib(drop)
    print(f"Reading {bib_file.name}")

    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    with bib_file.open() as f:
        db = bibtexparser.load(f, parser=parser)

    if not db.entries:
        print("No entries found in the .bib file.")
        return 1

    new_records: list[dict] = []
    tex_lines: list[str] = []
    for entry in db.entries:
        citekey = entry["ID"]
        rec = build_json_record(entry)
        if not args.dry_run:
            copy_assets(rec, citekey, drop)
        new_records.append(rec)
        tex_lines.append(build_latex_line(rec, entry.get("volume"), entry.get("pages")))

        # Summary line per entry
        title_short = rec["title"][:70] + ("..." if len(rec["title"]) > 70 else "")
        flags = []
        if rec["featured"]:
            flags.append("featured")
        if rec["projects"]:
            flags.append(f"projects={','.join(rec['projects'])}")
        flag_str = f" [{' '.join(flags)}]" if flags else ""
        print(f"  + {rec['id']}: {title_short}{flag_str}")

    if args.dry_run:
        print("\n--- LaTeX entries (dry run) ---")
        for line in tex_lines:
            print(line)
        print("\n--- JSON entries (dry run) ---")
        print(json.dumps(new_records, indent=2, ensure_ascii=False))
        return 0

    added, skipped = insert_into_publications(new_records)
    if skipped:
        print(f"\nSkipped {len(skipped)} duplicate id(s): {', '.join(skipped)}")
    print(f"Added {added} entr{'y' if added == 1 else 'ies'} to data/publications.json.")

    # Only insert LaTeX entries that actually got added to the JSON (filter by id).
    added_ids = {r["id"] for r in new_records} - set(skipped)
    fresh_tex = [
        line for line, r in zip(tex_lines, new_records) if r["id"] in added_ids
    ]
    if fresh_tex:
        insert_latex_entries(fresh_tex)
        print(f"Inserted {len(fresh_tex)} entr{'y' if len(fresh_tex) == 1 else 'ies'} into {CV_TEX.relative_to(REPO_ROOT)}.")

    if not args.no_build and (added or not new_records):
        if added:
            ok = compile_pdf()
            if not ok:
                print("\n(continuing despite PDF build failure — JSON and .tex changes are still saved)")

    print("\nDone. Review the diff with `git status` / `git diff` and commit when ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
