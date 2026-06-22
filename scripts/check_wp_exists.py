#!/usr/bin/env python3
"""Step 1: check whether each Bulgarian name already exists on bg.wikipedia.

Uses the MediaWiki API (batched, 50 titles per request) to fill:
  wp_exists : yes | redirect | no
  wp_url    : canonical article URL when it exists

Resumable: only checks rows whose wp_exists is still empty.
"""
from __future__ import annotations

import time
import requests

from common import add_note, load_rows, save_rows

API = "https://bg.wikipedia.org/w/api.php"
UA = "red-book-tracker/0.1 (Wikipedia article-creation project)"
BATCH = 50


def article_url(title: str) -> str:
    return "https://bg.wikipedia.org/wiki/" + title.replace(" ", "_")


SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})


def _get(params: dict) -> dict:
    """POST the API request with backoff that honors Retry-After / 429."""
    wait = 5.0
    for attempt in range(6):
        resp = SESSION.post(API, data=params, timeout=60)
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


def check_batch(titles: list[str]) -> dict[str, dict]:
    """Return {original_title: {exists, redirect, canonical}}."""
    data = _get(
        {
            "action": "query",
            "format": "json",
            "prop": "info",
            "titles": "|".join(titles),
            "redirects": 1,
        }
    ).get("query", {})

    # Map normalized/redirected titles back to what we queried.
    norm = {n["from"]: n["to"] for n in data.get("normalized", [])}
    redirs = {r["from"]: r["to"] for r in data.get("redirects", [])}
    pages = {p.get("title"): p for p in data.get("pages", {}).values()}

    out: dict[str, dict] = {}
    for original in titles:
        step1 = norm.get(original, original)
        was_redirect = step1 in redirs
        final = redirs.get(step1, step1)
        page = pages.get(final, {})
        exists = "missing" not in page and page.get("pageid", 0) != 0
        out[original] = {
            "exists": exists,
            "redirect": was_redirect,
            "canonical": page.get("title", final),
        }
    return out


def main() -> None:
    rows = load_rows()
    todo = [r for r in rows if not r["wp_exists"]]
    print(f"Checking {len(todo)} of {len(rows)} rows for bg.wikipedia existence")

    by_title = {}
    for r in todo:
        by_title.setdefault(r["bg_name"], []).append(r)

    titles = list(by_title)
    found = 0
    for i in range(0, len(titles), BATCH):
        chunk = titles[i : i + BATCH]
        results = check_batch(chunk)

        for title, info in results.items():
            for r in by_title[title]:
                if info["exists"]:
                    r["wp_exists"] = "redirect" if info["redirect"] else "yes"
                    r["wp_url"] = article_url(info["canonical"])
                    found += 1
                    if info["redirect"]:
                        add_note(r, f"WP redirect -> {info['canonical']}")
                else:
                    r["wp_exists"] = "no"
                    r["wp_url"] = ""
        save_rows(rows)  # checkpoint after each batch
        print(f"  {min(i + BATCH, len(titles))}/{len(titles)} titles done")
        time.sleep(1.5)

    exists = sum(1 for r in rows if r["wp_exists"] in ("yes", "redirect"))
    missing = sum(1 for r in rows if r["wp_exists"] == "no")
    print(f"\nDone. exists/redirect={exists}, missing={missing}")


if __name__ == "__main__":
    main()
