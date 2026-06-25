#!/usr/bin/env python3
"""Fill Wikidata Bulgarian label and scientific name into tracking.csv.

For each row with a `wikidata_qid`, fetches the item and writes:
  wd_bg_name : labels.bg (empty when Wikidata has no Bulgarian label)
  wd_taxon   : P225 scientific name (preferred rank, else first value)

Resumable: only processes rows with an empty `wd_bg_name` and `wd_taxon`
unless --force. Checkpoints after each API batch.

Usage:
    python scripts/fetch_wikidata_labels.py
    python scripts/fetch_wikidata_labels.py --force
    python scripts/fetch_wikidata_labels.py --ids 11 12 14
"""
from __future__ import annotations

import argparse
import time

import requests

from common import load_rows, save_rows

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


def bg_label(ent: dict) -> str:
    v = ent.get("labels", {}).get("bg")
    return v["value"] if v else ""


def scientific_name(ent: dict) -> str:
    claims = ent.get("claims", {}).get("P225", [])
    pools = (
        [c for c in claims if c.get("rank") == "preferred"],
        claims,
    )
    for pool in pools:
        for claim in pool:
            snak = claim.get("mainsnak", {})
            if snak.get("snaktype") != "value":
                continue
            value = snak.get("datavalue", {}).get("value")
            if isinstance(value, str) and value:
                return value
    return ""


def fetch_entities(qids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(qids), BATCH):
        chunk = qids[i : i + BATCH]
        data = _get(
            {
                "action": "wbgetentities",
                "format": "json",
                "ids": "|".join(chunk),
                "props": "labels|claims",
                "languages": "bg",
            }
        )
        for qid, ent in data.get("entities", {}).items():
            if not ent.get("missing"):
                out[qid] = ent
        time.sleep(1.0)
    return out


def needs_fill(row: dict, force: bool) -> bool:
    if not row["wikidata_qid"].strip():
        return False
    if force:
        return True
    return not row.get("wd_bg_name", "").strip() and not row.get("wd_taxon", "").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="refresh rows that already have wd_* values")
    ap.add_argument("--ids", nargs="*", help="only these tracking ids (space-separated)")
    args = ap.parse_args()

    rows = load_rows()
    by_id = {r["id"]: r for r in rows}

    if args.ids:
        missing = [i for i in args.ids if i not in by_id]
        if missing:
            raise SystemExit(f"Unknown ids: {', '.join(missing)}")
        todo = [by_id[i] for i in args.ids if needs_fill(by_id[i], args.force)]
    else:
        todo = [r for r in rows if needs_fill(r, args.force)]

    print(f"Fetching Wikidata labels for {len(todo)} rows")
    if not todo:
        return

    qids = sorted({r["wikidata_qid"] for r in todo})
    print(f"Querying {len(qids)} unique QIDs...")
    entities = fetch_entities(qids)

    filled = no_bg = no_p225 = missing_item = 0
    mismatches: list[str] = []

    for r in todo:
        qid = r["wikidata_qid"]
        ent = entities.get(qid)
        if not ent:
            missing_item += 1
            continue

        wd_bg = bg_label(ent)
        wd_taxon = scientific_name(ent)
        r["wd_bg_name"] = wd_bg
        r["wd_taxon"] = wd_taxon
        filled += 1

        if not wd_bg:
            no_bg += 1
        if not wd_taxon:
            no_p225 += 1

        if wd_bg and wd_bg != r["bg_name"]:
            mismatches.append(f"  id {r['id']:>4}  bg: {r['bg_name']!r} -> {wd_bg!r}  ({qid})")
        if wd_taxon and wd_taxon != r["taxon"]:
            mismatches.append(f"  id {r['id']:>4}  taxon: {r['taxon']!r} -> {wd_taxon!r}  ({qid})")

    save_rows(rows)

    print(f"\nDone. filled={filled}, missing_item={missing_item}, no_bg_label={no_bg}, no_P225={no_p225}")
    if mismatches:
        print(f"\n{len(mismatches)} value(s) differ from list bg_name/taxon (first 20):")
        for line in mismatches[:20]:
            print(line)
        if len(mismatches) > 20:
            print(f"  ... and {len(mismatches) - 20} more")


if __name__ == "__main__":
    main()
