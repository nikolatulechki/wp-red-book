"""Shared helpers for the Red Book tracking pipeline."""
from __future__ import annotations

import csv
import html
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRACKING = REPO / "tracking.csv"
MISMATCHES = REPO / "tracking_taxon_mismatches.csv"

COLUMNS = [
    "id",
    "group",
    "redbook_vol",
    "bg_name",
    "taxon",
    "redbook_status",
    "wp_exists",
    "wp_url",
    "wikidata_qid",
    "redbook_url",
    "rb_bg_name",
    "rb_taxon",
    "wd_bg_name",
    "wd_taxon",
    "wd_rb_taxon_match",
    "content_status",
    "wd_linked",
    "notes",
]

# Source-data corrections (the Wikipedia list has a few typos that would
# otherwise break taxon matching). Keyed by the taxon string as parsed.
TAXON_FIXES = {
    "Parvotrisetum myrianthum myrianthum": "Parvotrisetum myrianthum",
    "Phellinus hippopha\u00a8icola": "Phellinus hippophaeicola",
    "Centaurea finazzer": "Centaurea finazzeri",
}

# Cyrillic letters that are visual look-alikes of Latin ones occasionally
# slip into source Latin names; fold them to Latin for matching.
HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
        "к": "k", "м": "m", "н": "h", "т": "t", "в": "b", "і": "i", "ј": "j",
    }
)


def load_rows(path: Path = TRACKING) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for col in COLUMNS:
            r.setdefault(col, "")
    return rows


def save_rows(rows: list[dict], path: Path = TRACKING) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def save_mismatch_sheet(rows: list[dict], path: Path = MISMATCHES) -> int:
    """Write rows where wd_rb_taxon_match is no or empty (missing wd/rb taxon)."""
    mismatches = [r for r in rows if r.get("wd_rb_taxon_match") != "yes"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(mismatches)
    return len(mismatches)


def article_url(title: str) -> str:
    return "https://bg.wikipedia.org/wiki/" + title.replace(" ", "_")


def clean_taxon(taxon: str) -> str:
    return TAXON_FIXES.get(taxon, taxon)


def norm_taxon(name: str) -> str:
    """Normalise a Latin name for comparison."""
    name = html.unescape(name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    name = name.replace(" ssp. ", " subsp. ")
    return name.translate(HOMOGLYPHS)


def taxa_match(a: str, b: str) -> bool:
    return norm_taxon(clean_taxon(a)) == norm_taxon(clean_taxon(b))


def add_note(row: dict, note: str) -> None:
    existing = row.get("notes", "").strip()
    parts = [p for p in existing.split("; ") if p]
    if note not in parts:
        parts.append(note)
    row["notes"] = "; ".join(parts)
