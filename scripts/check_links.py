#!/usr/bin/env python3
"""Pre-flight a draft .mw article: which [[links]] / [[Категория:…]] are red?

Parses every internal wikilink and category out of the given .mw files and asks
the bg.wikipedia API which target pages actually exist (following redirects).
Reports red links per file so you fix wrong family names / missing categories
*before* pushing. File: / Файл: (Commons) links are listed but not resolved.

Exit code is non-zero if any non-category red link is found.

Usage:
    python scripts/check_links.py outbox/Алпийски_корал.mw [more.mw ...]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

BG_API = "https://bg.wikipedia.org/w/api.php"
UA = "red-book-tracker/0.1 (Wikipedia article-creation project)"
BATCH = 50

LINK = re.compile(r"\[\[([^\]\[]+?)\]\]")
FILE_PREFIXES = ("файл:", "file:", "image:", "медия:", "media:")


def link_targets(text: str) -> tuple[set[str], set[str], set[str]]:
    """Return (page_targets, category_targets, file_targets)."""
    pages: set[str] = set()
    cats: set[str] = set()
    files: set[str] = set()
    for raw in LINK.findall(text):
        target = raw.split("|", 1)[0].strip()
        if not target:
            continue
        target = target.lstrip(":").strip()
        target = target.split("#", 1)[0].strip()  # drop section anchor
        if not target:
            continue
        low = target.lower()
        if low.startswith(("категория:", "category:")):
            cats.add(target)
        elif low.startswith(FILE_PREFIXES):
            files.add(target)
        else:
            pages.add(target)
    return pages, cats, files


def exists(titles: list[str]) -> dict[str, bool]:
    """Map each title -> exists on bgwiki (redirects followed)."""
    out: dict[str, bool] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    for i in range(0, len(titles), BATCH):
        chunk = titles[i : i + BATCH]
        params = {
            "action": "query",
            "format": "json",
            "prop": "info",
            "redirects": "1",
            "titles": "|".join(chunk),
        }
        wait = 5.0
        for attempt in range(6):
            resp = session.get(BG_API, params=params, timeout=60)
            if resp.status_code == 429:
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            resp.raise_for_status()
            break
        data = resp.json().get("query", {})

        # Build normalized/redirect maps so we can attribute results to inputs.
        norm = {n["from"]: n["to"] for n in data.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in data.get("redirects", [])}
        resolved = {p.get("title"): ("missing" not in p) for p in data.get("pages", {}).values()}

        for title in chunk:
            t = norm.get(title, title)
            t = redir.get(t, t)
            out[title] = resolved.get(t, False)
        time.sleep(0.5)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", help=".mw files to check")
    args = ap.parse_args()

    per_file: dict[str, tuple[set[str], set[str], set[str]]] = {}
    all_titles: set[str] = set()
    for f in args.files:
        p = Path(f)
        if not p.exists():
            print(f"!! not found: {f}", file=sys.stderr)
            sys.exit(2)
        pages, cats, files = link_targets(p.read_text(encoding="utf-8"))
        per_file[f] = (pages, cats, files)
        all_titles |= pages | cats

    present = exists(sorted(all_titles)) if all_titles else {}

    any_red = False
    for f, (pages, cats, files) in per_file.items():
        red_pages = sorted(t for t in pages if not present.get(t, False))
        red_cats = sorted(t for t in cats if not present.get(t, False))
        print(f"\n=== {f} ===")
        print(f"  links={len(pages)} categories={len(cats)} files={len(files)}")
        if red_pages:
            any_red = True
            print("  RED LINKS (fix or unlink before push):")
            for t in red_pages:
                print(f"    - [[{t}]]")
        if red_cats:
            print("  MISSING CATEGORY PAGES (verify the Bulgarian family/genus name):")
            for t in red_cats:
                print(f"    - [[{t}]]")
        if files:
            print("  files (not checked — live on Commons):")
            for t in sorted(files):
                print(f"    - [[{t}]]")
        if not red_pages and not red_cats:
            print("  OK — all article/category links resolve.")

    sys.exit(1 if any_red else 0)


if __name__ == "__main__":
    main()
