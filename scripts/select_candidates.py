#!/usr/bin/env python3
"""Pick species that are *truly* missing a bg.wikipedia article.

A row is a real candidate only if ALL of:
  - content_status == 'todo'           (not already drafted/published by us)
  - wp_exists == 'no'                  (tracker thinks it's missing)
  - wikidata_qid is set                (needed for the Taxobox + sitelink)
  - redbook_url is set                 (needed for the prose + citation)
  - the QID has NO `bgwiki` sitelink   (guards against false missings, where the
    article exists under a different Bulgarian title — see sweep_wp_via_wikidata)

Prints a table of the first N candidates. Rows that pass the local filters but
turn out to already have a sitelink are reported separately as false missings.

Usage:
    python scripts/select_candidates.py --n 10
    python scripts/select_candidates.py --n 5 --group animals
    python scripts/select_candidates.py --n 5 --status CR
"""
from __future__ import annotations

import argparse
import time

import requests

from common import load_rows

WD_API = "https://www.wikidata.org/w/api.php"
UA = "red-book-tracker/0.1 (Wikipedia article-creation project)"
BATCH = 50


def _get(session: requests.Session, params: dict) -> dict:
    wait = 5.0
    for attempt in range(8):
        resp = session.get(WD_API, params=params, timeout=60)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            sleep = float(retry_after) if retry_after else wait
            print(f"    429; sleeping {sleep:.0f}s (attempt {attempt + 1})")
            time.sleep(sleep)
            wait = min(wait * 2, 120)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("giving up after repeated 429s")


def bgwiki_sitelinks(qids: list[str]) -> dict[str, str | None]:
    """Return {qid: bgwiki title or None}."""
    out: dict[str, str | None] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    for i in range(0, len(qids), BATCH):
        chunk = qids[i : i + BATCH]
        data = _get(
            session,
            {
                "action": "wbgetentities",
                "format": "json",
                "ids": "|".join(chunk),
                "props": "sitelinks",
            },
        )
        for qid, ent in data.get("entities", {}).items():
            if ent.get("missing"):
                out[qid] = None
                continue
            sl = ent.get("sitelinks", {}).get("bgwiki")
            out[qid] = sl["title"] if sl else None
        time.sleep(1.0)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=10, help="how many candidates to return")
    ap.add_argument("--group", choices=["plants_fungi", "animals"], help="filter by group")
    ap.add_argument("--status", help="filter by redbook_status (CR/EN/VU/RE/EX)")
    args = ap.parse_args()

    rows = load_rows()
    pool = [
        r
        for r in rows
        if r.get("content_status", "todo") == "todo"
        and r["wp_exists"] == "no"
        and r["wikidata_qid"].strip()
        and r["redbook_url"].strip()
    ]
    if args.group:
        pool = [r for r in pool if r["group"] == args.group]
    if args.status:
        pool = [r for r in pool if r["redbook_status"] == args.status.upper()]

    if not pool:
        print("No rows match the local filters.")
        return

    # Verify against live Wikidata in id order until we have N real candidates.
    pool.sort(key=lambda r: int(r["id"]))
    qids = [r["wikidata_qid"] for r in pool]
    print(f"Checking bgwiki sitelinks for {len(qids)} candidate QIDs...")
    links = bgwiki_sitelinks(sorted(set(qids)))

    good: list[dict] = []
    false_missing: list[tuple[dict, str]] = []
    for r in pool:
        title = links.get(r["wikidata_qid"])
        if title:
            false_missing.append((r, title))
            continue
        good.append(r)
        if len(good) >= args.n:
            break

    print(f"\n=== {len(good)} candidate(s) ready to create ===")
    print(f"{'id':>4}  {'status':<6} {'vol':<5} {'bg_name':<32} {'taxon':<34} {'qid':<11} redbook_url")
    for r in good:
        print(
            f"{r['id']:>4}  {r['redbook_status']:<6} {r['redbook_vol']:<5} "
            f"{r['bg_name'][:31]:<32} {r['taxon'][:33]:<34} {r['wikidata_qid']:<11} {r['redbook_url']}"
        )

    if false_missing:
        print(f"\n!!! {len(false_missing)} false missing(s) — article already exists under another title.")
        print("    Run: python scripts/sweep_wp_via_wikidata.py  to correct tracking.csv")
        for r, title in false_missing[:10]:
            print(f"    id {r['id']:>4} {r['bg_name']}  ->  exists as '{title}' ({r['wikidata_qid']})")


if __name__ == "__main__":
    main()
