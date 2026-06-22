#!/usr/bin/env python3
"""Step 2: reconcile Latin taxa to Wikidata QIDs.

Uses the Wikidata reconciliation service (the OpenRefine-style API behind the
wikidata-pybot recon skill) restricted to taxon items (Q16521). The bundled
client's manifest path is stale for the current service, so we POST the
form-encoded `queries` payload to the base endpoint directly.

Fills:
  wikidata_qid : QID when confident (auto-match, or score >= MIN_SCORE)
  notes        : best low-confidence candidate when not confident

Resumable: only processes rows whose wikidata_qid is empty.
"""
from __future__ import annotations

import json
import time

import requests

from common import add_note, clean_taxon, load_rows, save_rows

ENDPOINT = "https://wikidata.reconci.link/en/api"
UA = "red-book-tracker/0.1 (Wikipedia article-creation project)"
TAXON_TYPE = "Q16521"
MIN_SCORE = 90.0
BATCH = 20

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})


def reconcile_batch(queries: dict[str, dict]) -> dict:
    wait = 5.0
    for attempt in range(8):
        try:
            resp = SESSION.post(
                ENDPOINT, data={"queries": json.dumps(queries)}, timeout=60
            )
        except requests.exceptions.RequestException as e:
            print(f"    connection error: {e}; sleeping {wait:.0f}s (attempt {attempt + 1})")
            time.sleep(wait)
            wait = min(wait * 2, 120)
            continue
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


def main() -> None:
    rows = load_rows()
    todo = [r for r in rows if not r["wikidata_qid"] and r["taxon"]]
    print(f"Reconciling {len(todo)} of {len(rows)} taxa to Wikidata")

    matched = low = nohit = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        queries = {
            str(j): {"query": clean_taxon(r["taxon"]), "type": TAXON_TYPE, "limit": 3}
            for j, r in enumerate(chunk)
        }
        data = reconcile_batch(queries)
        # The service returns the per-query mapping directly; older versions
        # wrapped it in {"results": ...}. Handle both.
        results = data.get("results", data) if isinstance(data, dict) else {}

        for j, r in enumerate(chunk):
            cands = results.get(str(j), {}).get("result", [])
            if not cands:
                nohit += 1
                add_note(r, "WD: no candidate")
                continue
            top = cands[0]
            score = float(top.get("score") or 0)
            if top.get("match") or score >= MIN_SCORE:
                r["wikidata_qid"] = top["id"]
                matched += 1
            else:
                low += 1
                add_note(r, f"WD: low score {top['id']} ({score:.0f}) {top.get('name','')}")

        save_rows(rows)  # checkpoint
        print(f"  {min(i + BATCH, len(todo))}/{len(todo)} taxa done")
        time.sleep(1.0)

    have = sum(1 for r in rows if r["wikidata_qid"])
    print(f"\nDone. matched this run={matched}, low={low}, no-candidate={nohit}")
    print(f"Total with QID: {have}/{len(rows)}")


if __name__ == "__main__":
    main()
