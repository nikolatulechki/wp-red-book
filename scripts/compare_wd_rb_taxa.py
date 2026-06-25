#!/usr/bin/env python3
"""Set wd_rb_taxon_match (yes/no) by comparing wd_taxon and rb_taxon.

Uses the same normalisation as build_redbook_map (case, whitespace,
homoglyphs, ssp./subsp.).

Usage:
    python scripts/compare_wd_rb_taxa.py
"""
from __future__ import annotations

from common import MISMATCHES, load_rows, save_mismatch_sheet, save_rows, taxa_match


def main() -> None:
    rows = load_rows()
    yes = no = empty = 0

    for r in rows:
        wd = r.get("wd_taxon", "").strip()
        rb = r.get("rb_taxon", "").strip()
        if not wd or not rb:
            r["wd_rb_taxon_match"] = ""
            empty += 1
        elif taxa_match(wd, rb):
            r["wd_rb_taxon_match"] = "yes"
            yes += 1
        else:
            r["wd_rb_taxon_match"] = "no"
            no += 1

    save_rows(rows)
    written = save_mismatch_sheet(rows)
    print(f"Done. match=yes {yes}, match=no {no}, incomplete {empty}")
    print(f"Wrote {written} rows to {MISMATCHES.name} ({no} mismatches + {empty} incomplete)")


if __name__ == "__main__":
    main()
