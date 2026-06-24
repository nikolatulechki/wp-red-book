#!/usr/bin/env python3
"""Pick species that are *truly* missing a bg.wikipedia article.

A row is a real candidate only if ALL of:
  - content_status == 'todo'           (not already drafted/published by us)
  - wp_exists == 'no'                  (tracker thinks it's missing)
  - wikidata_qid is set                (needed for the Taxobox + sitelink)
  - redbook_url is set                 (needed for the prose + citation)
  - the QID has NO `bgwiki` sitelink   (guards against false missings, where the
    article exists under a different Bulgarian title — see sweep_wp_via_wikidata)
  - the bg_name page does NOT exist on bgwiki (authoritative idempotency guard:
    a page can exist without a Wikidata sitelink, e.g. our own article whose
    step-6 link failed or whose tracking row was never committed — without this
    check we would re-select and re-create it)

Prints a table of the first N candidates. Rows that pass the local filters but
already exist on the wiki (sitelink OR live page) are reported separately so
they are never handed to the writer/publisher again.

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
BG_API = "https://bg.wikipedia.org/w/api.php"
UA = "red-book-tracker/0.1 (Wikipedia article-creation project)"
BATCH = 50


def _get(session: requests.Session, params: dict, *, api: str = WD_API) -> dict:
    wait = 5.0
    for attempt in range(8):
        resp = session.get(api, params=params, timeout=60)
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


def bgwiki_pages_exist(titles: list[str]) -> dict[str, bool]:
    """Return {title: page exists on bgwiki} (redirects followed)."""
    out: dict[str, bool] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    uniq = sorted({t for t in titles if t})
    for i in range(0, len(uniq), BATCH):
        chunk = uniq[i : i + BATCH]
        data = _get(
            session,
            {
                "action": "query",
                "format": "json",
                "prop": "info",
                "redirects": "1",
                "titles": "|".join(chunk),
            },
            api=BG_API,
        ).get("query", {})
        norm = {n["from"]: n["to"] for n in data.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in data.get("redirects", [])}
        resolved = {p.get("title"): ("missing" not in p) for p in data.get("pages", {}).values()}
        for title in chunk:
            t = norm.get(title, title)
            t = redir.get(t, t)
            out[title] = resolved.get(t, False)
        time.sleep(0.5)
    return out


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

    # Verify against the live wiki in id order until we have N real candidates.
    pool.sort(key=lambda r: int(r["id"]))
    qids = [r["wikidata_qid"] for r in pool]
    print(f"Checking bgwiki sitelinks for {len(qids)} candidate QIDs...")
    links = bgwiki_sitelinks(sorted(set(qids)))
    print(f"Checking bgwiki page existence for {len(pool)} candidate titles...")
    pages = bgwiki_pages_exist([r["bg_name"] for r in pool])

    good: list[dict] = []
    false_missing: list[tuple[dict, str]] = []
    for r in pool:
        title = links.get(r["wikidata_qid"])
        if title:
            false_missing.append((r, f"sitelink -> '{title}'"))
            continue
        # Authoritative guard: the target page may already exist even with no
        # Wikidata sitelink (our own article whose step-6 link/tracking lagged).
        if pages.get(r["bg_name"]):
            false_missing.append((r, "page already exists on bgwiki (no WD sitelink)"))
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
        print(f"\n!!! {len(false_missing)} already exist(s) — do NOT brief/publish these.")
        print("    Run: python scripts/sweep_wp_via_wikidata.py  to correct tracking.csv")
        for r, why in false_missing[:20]:
            print(f"    id {r['id']:>4} {r['bg_name']}  ->  {why} ({r['wikidata_qid']})")


if __name__ == "__main__":
    main()
