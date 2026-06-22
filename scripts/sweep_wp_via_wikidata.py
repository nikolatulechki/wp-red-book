#!/usr/bin/env python3
"""Find false missings: wp_exists=no but the Wikidata item already has a bgwiki sitelink.

Fills wp_exists, wp_url, and notes for rows where the article exists under a
different Bulgarian title than the Red Book list name.

Resumable: only processes rows with wp_exists=no and a non-empty wikidata_qid.
"""
from __future__ import annotations

import time

import requests

from common import add_note, article_url, load_rows, save_rows

WD_API = "https://www.wikidata.org/w/api.php"
UA = "red-book-tracker/0.1 (Wikipedia article-creation project)"
BATCH = 50


def _get(params: dict) -> dict:
    wait = 5.0
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
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


def fetch_bg_titles(qids: list[str]) -> dict[str, str | None]:
    """Return {qid: bgwiki title or None}."""
    out: dict[str, str | None] = {}
    for i in range(0, len(qids), BATCH):
        chunk = qids[i : i + BATCH]
        data = _get(
            {
                "action": "wbgetentities",
                "format": "json",
                "ids": "|".join(chunk),
                "props": "sitelinks",
            }
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
    rows = load_rows()
    todo = [r for r in rows if r["wp_exists"] == "no" and r["wikidata_qid"].strip()]
    print(f"Sweeping {len(todo)} rows (wp_exists=no with QID)")

    qids = sorted({r["wikidata_qid"] for r in todo})
    print(f"Fetching bgwiki sitelinks for {len(qids)} unique QIDs...")
    sitelinks = fetch_bg_titles(qids)

    alt_title = same_title = 0
    for r in todo:
        title = sitelinks.get(r["wikidata_qid"])
        if not title:
            continue
        r["wp_exists"] = "yes"
        r["wp_url"] = article_url(title)
        if title == r["bg_name"]:
            add_note(r, f"WP exists (confirmed via Wikidata sitelink on {r['wikidata_qid']})")
            same_title += 1
        else:
            add_note(
                r,
                f"Existing WP article under different title ({title}); "
                f"{r['wikidata_qid']} already has bgwiki sitelink",
            )
            alt_title += 1

    save_rows(rows)
    print(f"\nDone. alt-title={alt_title}, same-title={same_title}, unchanged={len(todo) - alt_title - same_title}")


if __name__ == "__main__":
    main()
