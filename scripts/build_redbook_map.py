#!/usr/bin/env python3
"""Step 3: map taxa to their Red Book (e-ecodb.bas.bg) article URLs.

The vol1 (plants & fungi) and vol2 (animals) index pages are static
windows-1251 HTML tables. Each row links the article file with the Latin
name in <i> tags, e.g.:

    <a href="Rokessle.html"><i>Romanogobio kessleri</i></a>

The article filenames are abbreviated and cannot be guessed, so we scrape
the indexes to build a {latin name -> URL} map, save it, and fill the
`redbook_url` column by exact (normalised) name match.
"""
from __future__ import annotations

import html
import json
import re

import requests

from common import REPO, add_note, clean_taxon, load_rows, save_rows

# Cyrillic letters that are visual look-alikes of Latin ones occasionally
# slip into the Red Book's Latin names; fold them to Latin for matching.
HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
        "к": "k", "м": "m", "н": "h", "т": "t", "в": "b", "і": "i", "ј": "j",
    }
)

BASES = {
    "vol1": "http://e-ecodb.bas.bg/rdb/bg/vol1/",
    "vol2": "http://e-ecodb.bas.bg/rdb/bg/vol2/",
}
INDEX = "texts.html"
UA = "red-book-tracker/0.1 (Wikipedia article-creation project)"
DATA = REPO / "data"

ROW = re.compile(r'href="([^"]+\.html)"><i>([^<]+)</i>')


def norm(name: str) -> str:
    """Normalise a Latin name for matching."""
    name = html.unescape(name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    name = name.replace(" ssp. ", " subsp. ")  # unify subspecies marker
    return name.translate(HOMOGLYPHS)


def scrape() -> dict[str, str]:
    DATA.mkdir(exist_ok=True)
    mapping: dict[str, str] = {}
    for vol, base in BASES.items():
        resp = requests.get(base + INDEX, headers={"User-Agent": UA}, timeout=60)
        resp.raise_for_status()
        html = resp.content.decode("windows-1251", errors="replace")
        (DATA / f"{vol}_texts.html").write_text(html, encoding="utf-8")

        found = 0
        for href, latin in ROW.findall(html):
            key = norm(latin)
            url = base + href
            mapping.setdefault(key, url)  # first wins; sort variants repeat rows
            found += 1
        print(f"{vol}: {found} rows, {len(mapping)} unique names so far")

    (DATA / "redbook_index.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=0, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Saved map with {len(mapping)} unique Latin names")
    return mapping


def main() -> None:
    mapping = scrape()
    rows = load_rows()

    filled = missing = 0
    unmatched = []
    for r in rows:
        if r["redbook_url"]:
            continue
        # Try both the corrected and the raw taxon (some index entries faithfully
        # reproduce source typos that clean_taxon would otherwise "fix").
        url = mapping.get(norm(clean_taxon(r["taxon"]))) or mapping.get(norm(r["taxon"]))
        if url:
            r["redbook_url"] = url
            filled += 1
            r["notes"] = "; ".join(
                p for p in r["notes"].split("; ") if p and p != "RB: no index match"
            )
        else:
            missing += 1
            unmatched.append(r)
            add_note(r, "RB: no index match")

    save_rows(rows)
    have = sum(1 for r in rows if r["redbook_url"])
    print(f"\nFilled this run={filled}, unmatched={missing}")
    print(f"Total with redbook_url: {have}/{len(rows)}")
    if unmatched:
        print("\nUnmatched taxa:")
        for r in unmatched:
            print(f"  {r['id']:>4} {r['group']:<12} {r['taxon']}")


if __name__ == "__main__":
    main()
