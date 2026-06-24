#!/usr/bin/env python3
"""Publish outbox .mw articles to bg.wikipedia via the MediaWiki API (seconds, not minutes).

Replaces the slow mega git-remote-mediawiki clone for new-article creation. Reads
wikitext from outbox/<Title>.mw (falls back to wiki/articles/ for legacy paths).

Auth uses the same bot password as wikipedia-git (git credential helper).

Creating new pages (default): reads outbox/<Title>.mw, createonly, archives the
draft to wiki/articles/ and records its base revid.

Editing existing pages (--allow-existing): reads outbox/ or the wiki/articles/
mirror, and pushes with the synced baserevid so a concurrent/human edit triggers
an EditConflict instead of being clobbered. Run sync_articles.py first.

Usage:
    .venv/bin/python scripts/publish_api.py Винчелистен_лопен
    .venv/bin/python scripts/publish_api.py outbox/Винчелистен_лопен.mw
    PUBLISH_SUMMARY="нова статия" .venv/bin/python scripts/publish_api.py Title1 Title2
    .venv/bin/python scripts/publish_api.py --dry-run Винчелистен_лопен
    .venv/bin/python scripts/publish_api.py --allow-existing --summary "..." Алепска_млечка
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTBOX = REPO / "outbox"
LEGACY = REPO / "wiki" / "articles"
DEFAULT_SUMMARY = "нова статия от Червената книга на България"

from article_store import get_base, record_revision  # noqa: E402
from common import add_note, load_rows, save_rows  # noqa: E402
from mw_client import EditConflict, MediaWikiClient  # noqa: E402


def reconcile_existing(title: str) -> bool:
    """Mark tracking.csv so an already-live page is never re-selected.

    Returns True if a row was updated. Sets wp_exists=yes and (if still todo)
    content_status=published_bot for the row whose bg_name matches `title`.
    """
    rows = load_rows()
    changed = False
    for r in rows:
        if r["bg_name"].replace("_", " ") == title.replace("_", " "):
            if r.get("wp_exists") != "yes":
                r["wp_exists"] = "yes"
                changed = True
            if r.get("content_status", "todo") == "todo":
                r["content_status"] = "published_bot"
                add_note(r, "reconciled by publish_api: page already existed")
                changed = True
    if changed:
        save_rows(rows)
    return changed


def resolve_mw_file(arg: str) -> tuple[Path, str]:
    """Return (path, wiki_title) for a title or file argument."""
    p = Path(arg)
    if p.suffix == ".mw":
        if not p.is_absolute():
            p = (REPO / p).resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        title = p.stem.replace("_", " ")
        return p, title

    title_key = arg.replace(" ", "_")
    for candidate in (OUTBOX / f"{title_key}.mw", LEGACY / f"{title_key}.mw"):
        if candidate.is_file():
            return candidate, arg.replace("_", " ")
    raise FileNotFoundError(
        f"no .mw for {arg!r} — expected outbox/{title_key}.mw"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("targets", nargs="+", help="page title or path to .mw file")
    ap.add_argument(
        "--summary",
        default=os.environ.get("PUBLISH_SUMMARY", DEFAULT_SUMMARY),
        help="edit summary (or set PUBLISH_SUMMARY)",
    )
    ap.add_argument("--dry-run", action="store_true", help="validate only, no API writes")
    ap.add_argument(
        "--no-purge",
        action="store_true",
        help="skip post-publish purge (Taxobox refresh)",
    )
    ap.add_argument(
        "--allow-existing",
        action="store_true",
        help="edit even if the page already exists (default: createonly)",
    )
    ap.add_argument(
        "--keep-outbox",
        action="store_true",
        help="do not move published .mw to wiki/articles/ (default: archive after publish)",
    )
    args = ap.parse_args()

    jobs: list[tuple[Path, str, str]] = []
    for target in args.targets:
        try:
            path, title = resolve_mw_file(target)
        except FileNotFoundError as exc:
            print(f"!! {exc}", file=sys.stderr)
            sys.exit(2)
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            print(f"!! empty file: {path}", file=sys.stderr)
            sys.exit(2)
        jobs.append((path, title, text))

    if args.dry_run:
        print(f"dry-run: would publish {len(jobs)} page(s) with summary={args.summary!r}")
        for path, title, text in jobs:
            print(f"  {title!r}  ({len(text)} bytes)  <- {path.relative_to(REPO)}")
        return

    client = MediaWikiClient()
    published: list[str] = []
    skipped: list[str] = []

    for path, title, text in jobs:
        rel = path.relative_to(REPO)
        # Idempotency net: never re-create a live page. Skip it (don't abort the
        # whole batch) and reconcile tracking.csv so selection won't pick it again.
        if client.page_exists(title) and not args.allow_existing:
            reconciled = reconcile_existing(title)
            note = " (tracking.csv reconciled)" if reconciled else ""
            print(
                f"-- SKIP {title!r}: already exists on bgwiki{note}. "
                "Use --allow-existing only to intentionally overwrite.",
                file=sys.stderr,
            )
            skipped.append(title)
            continue

        # Conflict-safe edits: send the synced base revision so a concurrent
        # (e.g. human) edit is rejected instead of silently overwritten.
        baserevid = basetimestamp = None
        if args.allow_existing:
            base = get_base(title)
            if base is None:
                live = client.get_page(title)
                baserevid, basetimestamp = live.revid, live.timestamp
                print(
                    f"   (no synced base for {title!r}; using live revid {baserevid}. "
                    "Run sync_articles.py for a reviewed base.)"
                )
            else:
                baserevid = base.get("revid")
                basetimestamp = base.get("timestamp")

        print(f"publishing {title!r} from {rel} ...")
        try:
            result = client.edit_page(
                title,
                text,
                args.summary,
                createonly=not args.allow_existing,
                baserevid=baserevid,
                basetimestamp=basetimestamp,
            )
        except EditConflict as exc:
            print(
                f"!! {exc}\n   The live page moved since your base. "
                f"Re-sync: scripts/sync_articles.py --titles {title!r}",
                file=sys.stderr,
            )
            sys.exit(4)
        if result.get("result") != "Success":
            print(f"!! edit failed for {title!r}: {result}", file=sys.stderr)
            sys.exit(1)
        newrevid = result.get("newrevid")
        print(f"  ✓ {result.get('result')}  revision={newrevid or '?'}")
        if newrevid:
            record_revision(title, newrevid, result.get("newtimestamp"))
        if not args.no_purge:
            client.purge(title)
            print("  ✓ purged")
        # Keep outbox = pending-only: archive the published draft to the
        # reference mirror so it can never be re-published from outbox.
        if not args.keep_outbox and path.parent == OUTBOX:
            LEGACY.mkdir(parents=True, exist_ok=True)
            dest = LEGACY / path.name
            path.replace(dest)
            print(f"  ✓ archived -> {dest.relative_to(REPO)}")
        published.append(title)

    print(f"\n=== done. published: {' '.join(published) or '(none)'} ===")
    if skipped:
        print(f"=== skipped (already exist): {' '.join(skipped)} ===")
    if published:
        print("next: .venv/bin/python scripts/link_wikidata_sitelinks.py --ids <ids>")
        print("      then update tracking.csv + bot log (wiki/bot/bot-pages/)")
    if skipped and not published:
        sys.exit(3)


if __name__ == "__main__":
    main()
