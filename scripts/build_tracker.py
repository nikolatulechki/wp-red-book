#!/usr/bin/env python3
"""Parse the Red Book species list (.mw) into a tracking sheet (CSV).

Source : wiki/species-list/Списък_на_видовете_в_Червената_книга_на_Република_България.mw
Output : tracking.csv

Each source line looks like:
    * [[Bulgarian name]] ([[Latin taxon]]) – STATUS

The script is robust to a few malformed lines (it extracts all [[...]]
wikilinks plus the trailing 2-letter status code) and reports anything it
could not parse so it can be fixed by hand.

The tracking sheet keeps one row per species with columns for every step of
the article-creation workflow; the lookup columns are left empty and filled
in later stages.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = (
    REPO
    / "wiki"
    / "species-list"
    / "Списък_на_видовете_в_Червената_книга_на_Република_България.mw"
)
OUT = REPO / "tracking.csv"

SECTIONS = {
    "Растения и гъби": ("plants_fungi", "vol1"),
    "Животни": ("animals", "vol2"),
}

VALID_STATUS = {"CR", "EN", "VU", "RE", "EX"}

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
STATUS = re.compile(r"\b(CR|EN|VU|RE|EX)\b\s*$")
HEADING = re.compile(r"^==\s*(.+?)\s*==")
# A well-formed entry: * [[bg]] ([[taxon]]) – XX
CANONICAL = re.compile(
    r"^\*\s*\[\[[^\]]+\]\]\s*\(\[\[[^\]]+\]\]\)\s*[–-]\s*(CR|EN|VU|RE|EX)\s*$"
)


# Latin scientific names use only these characters
TAXON_OK = re.compile(r"^[A-Za-z .\-×]+$")


def taxon_warnings(taxon: str) -> list[str]:
    warns = []
    if not TAXON_OK.match(taxon):
        warns.append("unexpected char in taxon")
    words = taxon.split()
    if len(words) >= 2 and words[-1] == words[-2]:
        warns.append("duplicated word in taxon")
    return warns

COLUMNS = [
    "id",
    "group",
    "redbook_vol",
    "bg_name",          # Wikipedia title (Bulgarian)
    "taxon",            # Latin scientific name
    "redbook_status",   # CR / EN / VU / RE / EX
    "wp_exists",        # yes / no / redirect  (step 1)
    "wp_url",           # (step 1)
    "wikidata_qid",     # (step 2)
    "redbook_url",      # (step 3)
    "rb_bg_name",       # exact Bulgarian from e-ecodb index (step 3)
    "rb_taxon",         # exact Latin from e-ecodb index (step 3)
    "content_status",   # todo / draft / created / published  (step 4)
    "notes",
]


def parse() -> tuple[list[dict], list[tuple[int, str]]]:
    rows: list[dict] = []
    problems: list[tuple[int, str]] = []
    group = vol = None
    seen: set[str] = set()
    idx = 0

    for lineno, raw in enumerate(SRC.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip()

        h = HEADING.match(line)
        if h:
            section = h.group(1)
            group, vol = SECTIONS.get(section, (None, None))
            continue

        if not line.lstrip().startswith("*"):
            continue
        if group is None:
            continue

        links = WIKILINK.findall(line)
        status_match = STATUS.search(line)
        status = status_match.group(1) if status_match else ""

        if not links or status not in VALID_STATUS:
            problems.append((lineno, line))
            # still record what we can, flagged in notes
        bg = links[0].strip() if links else ""
        taxon = (links[1].strip() if len(links) > 1 else links[0].strip()) if links else ""

        if not bg:
            problems.append((lineno, line))
            continue

        key = bg.lower()
        if key in seen:
            problems.append((lineno, f"DUPLICATE: {line}"))
            continue
        seen.add(key)

        idx += 1
        notes = []
        if not CANONICAL.match(line):
            notes.append(f"malformed source line {lineno}")
        notes.extend(taxon_warnings(taxon))
        note = "; ".join(notes)

        rows.append(
            {
                "id": idx,
                "group": group,
                "redbook_vol": vol,
                "bg_name": bg,
                "taxon": taxon,
                "redbook_status": status,
                "wp_exists": "",
                "wp_url": "",
                "wikidata_qid": "",
                "redbook_url": "",
                "rb_bg_name": "",
                "rb_taxon": "",
                "content_status": "todo",
                "notes": note,
            }
        )

    return rows, problems


def main() -> None:
    rows, problems = parse()

    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    plants = sum(1 for r in rows if r["group"] == "plants_fungi")
    animals = sum(1 for r in rows if r["group"] == "animals")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["redbook_status"]] = by_status.get(r["redbook_status"], 0) + 1

    print(f"Wrote {OUT.relative_to(REPO)} with {len(rows)} species")
    print(f"  plants & fungi : {plants}")
    print(f"  animals        : {animals}")
    print("  by status      : " + ", ".join(f"{k}={by_status[k]}" for k in sorted(by_status)))
    if problems:
        print(f"\n{len(problems)} line(s) needing manual review:")
        for lineno, text in problems:
            print(f"  L{lineno}: {text}")


if __name__ == "__main__":
    main()
