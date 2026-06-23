"""Shared helpers for the Red Book tracking pipeline."""
from __future__ import annotations

import csv
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRACKING = REPO / "tracking.csv"

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


def load_rows(path: Path = TRACKING) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_rows(rows: list[dict], path: Path = TRACKING) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def article_url(title: str) -> str:
    return "https://bg.wikipedia.org/wiki/" + title.replace(" ", "_")


def clean_taxon(taxon: str) -> str:
    return TAXON_FIXES.get(taxon, taxon)


def add_note(row: dict, note: str) -> None:
    existing = row.get("notes", "").strip()
    parts = [p for p in existing.split("; ") if p]
    if note not in parts:
        parts.append(note)
    row["notes"] = "; ".join(parts)
