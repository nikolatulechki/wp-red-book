#!/usr/bin/env python3
"""Sync local article clones from bg.wikipedia via the MediaWiki API.

Pulls the current wikitext of tracked pages into wiki/articles/<Title>.mw and
records the base revision in wiki/articles/.revids.json. This is the "always
up-to-date local clone" layer: run it before editing so your local copy (and the
baserevid used for conflict-safe pushes) matches the live wiki.

No git, no git-remote-mediawiki — just batched API reads.

Selection (default: all pages that exist on bgwiki per tracking.csv):
    python scripts/sync_articles.py                 # all wp_exists=yes rows
    python scripts/sync_articles.py --published     # only content_status=published_bot
    python scripts/sync_articles.py --ids 99 109
    python scripts/sync_articles.py --titles "Алепска млечка" "Винчелистен лопен"
    python scripts/sync_articles.py --local         # re-sync whatever is already mirrored

Use --check to report drift (local vs live revid) without writing files.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from article_store import (
    MIRROR,
    filename_to_title,
    get_base,
    record_revision,
    write_article,
)
from common import load_rows
from mw_client import MediaWikiClient


def select_titles(args: argparse.Namespace) -> list[str]:
    if args.titles:
        return list(args.titles)
    if args.local:
        return sorted(
            filename_to_title(p.name)
            for p in MIRROR.glob("*.mw")
        )
    rows = load_rows()
    if args.ids:
        wanted = set(args.ids)
        return [r["bg_name"] for r in rows if r["id"] in wanted and r["bg_name"].strip()]
    if args.published:
        return [
            r["bg_name"]
            for r in rows
            if r.get("content_status") == "published_bot" and r["bg_name"].strip()
        ]
    return [
        r["bg_name"]
        for r in rows
        if r.get("wp_exists") == "yes" and r["bg_name"].strip()
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", nargs="*", help="tracking ids to sync")
    ap.add_argument("--titles", nargs="*", help="explicit page titles to sync")
    ap.add_argument("--published", action="store_true", help="only content_status=published_bot")
    ap.add_argument("--local", action="store_true", help="re-sync titles already in the mirror")
    ap.add_argument("--check", action="store_true", help="report drift only; do not write files")
    args = ap.parse_args()

    titles = select_titles(args)
    if not titles:
        print("No titles selected.")
        return

    client = MediaWikiClient()
    print(f"Fetching {len(titles)} page(s) from bg.wikipedia ...")
    pages = client.get_pages(titles)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    synced = missing = unchanged = drifted = 0
    for title in titles:
        pc = pages.get(title)
        if pc is None or not pc.exists:
            print(f"  ✗ missing on wiki: {title}")
            missing += 1
            continue
        base = get_base(title)
        local_revid = base.get("revid") if base else None
        if args.check:
            if local_revid == pc.revid:
                unchanged += 1
            else:
                drifted += 1
                print(f"  ~ DRIFT {title}: local={local_revid} live={pc.revid}")
            continue
        if local_revid == pc.revid:
            unchanged += 1
        else:
            synced += 1
        write_article(title, pc.text)
        record_revision(title, pc.revid, pc.timestamp, synced_at=now)

    if args.check:
        print(f"\nchecked={len(titles)} up-to-date={unchanged} drifted={drifted} missing={missing}")
        sys.exit(1 if drifted else 0)
    print(f"\ndone. updated={synced} unchanged={unchanged} missing={missing}")
    print(f"mirror: {MIRROR.relative_to(MIRROR.parent.parent)}  index: .revids.json")


if __name__ == "__main__":
    main()
