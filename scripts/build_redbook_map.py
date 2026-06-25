#!/usr/bin/env python3
"""Step 3: map taxa to their Red Book (e-ecodb.bas.bg) article URLs.

The vol1 (plants & fungi) and vol2 (animals) index pages are static
windows-1251 HTML tables. Each row links the article file with the Latin
name in <i> tags, e.g.:

    <a href="Rokessle.html"><i>Romanogobio kessleri</i></a>

The article filenames are abbreviated and cannot be guessed, so we scrape
the indexes to build a {latin name -> URL} map, save it, and fill the
`redbook_url` column by exact (normalised) name match.

Also fills `rb_bg_name` and `rb_taxon` with the exact strings from the
index HTML (Bulgarian and Latin columns).
"""
from __future__ import annotations

import argparse
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

ROW_LATIN = re.compile(r'href="([^"]+\.html)"><i>([^<]+)</i>')
ROW_FULL = re.compile(
    r'<td><a href="([^"]+\.html)">([^<]+)</a></td>\s*'
    r'<td><a href="\1"><i>([^<]+)</i></a></td>\s*'
    r'<td[^>]*><a href="\1">(CR|EN|VU|RE|EX)</a></td>'
)


def norm(name: str) -> str:
    """Normalise a Latin name for matching."""
    name = html.unescape(name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    name = name.replace(" ssp. ", " subsp. ")  # unify subspecies marker
    return name.translate(HOMOGLYPHS)


def scrape(*, offline: bool = False) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    DATA.mkdir(exist_ok=True)
    mapping: dict[str, str] = {}
    by_url: dict[str, dict[str, str]] = {}
    for vol, base in BASES.items():
        cache = DATA / f"{vol}_texts.html"
        if offline:
            if not cache.is_file():
                raise FileNotFoundError(f"offline mode needs {cache}")
            page = cache.read_text(encoding="utf-8")
            print(f"{vol}: using cached {cache.name}")
        else:
            resp = requests.get(base + INDEX, headers={"User-Agent": UA}, timeout=120)
            resp.raise_for_status()
            page = resp.content.decode("windows-1251", errors="replace")
            cache.write_text(page, encoding="utf-8")

        found = 0
        for href, bg, latin, _status in ROW_FULL.findall(page):
            key = norm(latin)
            url = base + href
            mapping.setdefault(key, url)  # first wins; sort variants repeat rows
            by_url[url] = {
                "rb_bg_name": html.unescape(bg.strip()),
                "rb_taxon": html.unescape(latin.strip()),
            }
            found += 1
        print(f"{vol}: {found} rows, {len(mapping)} unique names so far")

    (DATA / "redbook_index.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=0, sort_keys=True),
        encoding="utf-8",
    )
    (DATA / "redbook_by_url.json").write_text(
        json.dumps(by_url, ensure_ascii=False, indent=0, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Saved map with {len(mapping)} unique Latin names")
    print(f"Saved {len(by_url)} URL entries with rb_bg_name / rb_taxon")
    return mapping, by_url


def fill_rb_names(rows: list[dict], by_url: dict[str, dict[str, str]]) -> int:
    filled = missing = 0
    for r in rows:
        url = r.get("redbook_url", "").strip()
        if not url:
            r["rb_bg_name"] = ""
            r["rb_taxon"] = ""
            continue
        info = by_url.get(url)
        if info:
            r["rb_bg_name"] = info["rb_bg_name"]
            r["rb_taxon"] = info["rb_taxon"]
            filled += 1
            r["notes"] = "; ".join(
                p for p in r["notes"].split("; ") if p and p != "RB: URL not in index"
            )
        else:
            r["rb_bg_name"] = ""
            r["rb_taxon"] = ""
            missing += 1
            add_note(r, "RB: URL not in index")
    return filled, missing


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--offline",
        action="store_true",
        help="parse cached data/vol*_texts.html instead of fetching",
    )
    args = ap.parse_args()

    mapping, by_url = scrape(offline=args.offline)
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

    rb_filled, rb_missing = fill_rb_names(rows, by_url)

    save_rows(rows)
    have = sum(1 for r in rows if r["redbook_url"])
    print(f"\nFilled redbook_url this run={filled}, unmatched={missing}")
    print(f"Total with redbook_url: {have}/{len(rows)}")
    print(f"Filled rb_bg_name/rb_taxon: {rb_filled}, URL not in index: {rb_missing}")
    if unmatched:
        print("\nUnmatched taxa:")
        for r in unmatched:
            print(f"  {r['id']:>4} {r['group']:<12} {r['taxon']}")


if __name__ == "__main__":
    main()
