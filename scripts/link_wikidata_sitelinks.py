#!/usr/bin/env python3
"""Set the `bgwiki` sitelink on each species' Wikidata item (Taxobox connector).

The bg {{Taxobox}} only auto-populates once the article is connected to its
Wikidata item via a `bgwiki` sitelink. Pushing the wikitext does NOT do this —
it is a separate write against wikidata.org. Run this AFTER the article is live.

Safe + resumable:
  - skips any item that already has a `bgwiki` sitelink (no conflicts);
  - records `wd_linked=yes` in tracking.csv and checkpoints after each write;
  - only touches rows we created unless you pass explicit --ids.

By default processes rows with content_status in {created, published_bot} that
are not yet `wd_linked`. Use --ids to restrict to specific tracking ids (the
usual case, right after creating a batch).

Auth: needs the Wikidata bot credential at ~/Projects/wiki/wikidata-pybot/
(user-config.py + user-password.py). PYWIKIBOT_DIR is set automatically.

Usage:
    python scripts/link_wikidata_sitelinks.py --ids 11 12 14
    python scripts/link_wikidata_sitelinks.py            # all eligible rows
    python scripts/link_wikidata_sitelinks.py --dry-run
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

PYBOT_DIR = Path.home() / "Projects" / "wiki" / "wikidata-pybot"
os.environ.setdefault("PYWIKIBOT_DIR", str(PYBOT_DIR))

from common import add_note, load_rows, save_rows  # noqa: E402

CREATED_STATUSES = {"created", "published", "published_bot"}


def eligible(rows: list[dict], ids: list[str] | None) -> list[dict]:
    if ids:
        wanted = set(ids)
        return [r for r in rows if r["id"] in wanted]
    return [
        r
        for r in rows
        if r.get("content_status") in CREATED_STATUSES
        and r.get("wd_linked", "") != "yes"
        and r["wikidata_qid"].strip()
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", nargs="*", help="restrict to these tracking ids")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, no writes")
    args = ap.parse_args()

    rows = load_rows()
    todo = eligible(rows, args.ids)
    todo = [r for r in todo if r["wikidata_qid"].strip() and r["bg_name"].strip()]
    if not todo:
        print("Nothing to link.")
        return

    print(f"{len(todo)} item(s) to link:")
    for r in todo:
        print(f"  id {r['id']:>4}  {r['wikidata_qid']:<11} -> bgwiki: {r['bg_name']}")
    if args.dry_run:
        print("\n--dry-run: no changes made.")
        return

    # Import pywikibot lazily so --dry-run / --help work without auth/config.
    from wikidata_pybot import delay, get_item, get_repo

    repo = get_repo()
    by_id = {r["id"]: r for r in rows}
    linked = skipped = failed = 0

    for r in todo:
        rid, qid, title = r["id"], r["wikidata_qid"], r["bg_name"]
        try:
            item = get_item(repo, qid)
            item.get()
            if "bgwiki" in item.sitelinks:
                existing = str(item.sitelinks["bgwiki"].title)
                print(f"  id {rid}: {qid} already has bgwiki -> {existing}; marking linked")
                by_id[rid]["wd_linked"] = "yes"
                skipped += 1
            else:
                item.setSitelink(
                    {"site": "bgwiki", "title": title},
                    summary="bot: add bgwiki sitelink (Red Book article)",
                )
                by_id[rid]["wd_linked"] = "yes"
                add_note(by_id[rid], "bgwiki sitelink set by bot")
                print(f"  id {rid}: linked {qid} -> {title}")
                linked += 1
                delay(1)
        except Exception as e:  # noqa: BLE001
            print(f"  id {rid}: FAILED {qid} ({e})")
            failed += 1
        save_rows(rows)  # checkpoint after each item

    print(f"\nDone. linked={linked}, already-linked={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
