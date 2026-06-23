#!/usr/bin/env python3
"""Gather the two source documents needed to write an article, per tracking id.

For each id it:
  1. downloads the Red Book entry (windows-1251), strips it to plain text, saves
     it to /tmp/rb/<id>.txt, and prints a short preview;
  2. fetches the Wikidata item and prints the facts the article/Taxobox needs:
     Latin name (P225), parent taxa (P171) with their bg labels + rank (so you
     can name the family), taxon rank (P105), image (P18), IUCN status (P141),
     Commons category (P935), and bg label + aliases (other Bulgarian names).

This replaces the ad-hoc curl-to-API calls done by hand each session.

Usage:
    python scripts/fetch_sources.py 11 12 14
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

from common import load_rows

UA = "RedBookBot/1.0 (https://bg.wikipedia.org/wiki/User:BOTulechki; article-creation)"
ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"
OUT = Path("/tmp/rb")

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"[ \t]+")
BLANKS = re.compile(r"\n\s*\n\s*\n+")


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def redbook_text(url: str) -> str:
    raw = http_get(url)
    page = raw.decode("windows-1251", errors="replace")
    page = re.sub(r"(?is)<script.*?</script>", " ", page)
    page = re.sub(r"(?is)<style.*?</style>", " ", page)
    page = page.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    page = re.sub(r"(?i)</(p|tr|div|h[1-6]|li)>", "\n", page)
    text = TAG.sub("", page)
    text = html.unescape(text)
    text = WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = BLANKS.sub("\n\n", text).strip()
    return text


def entity(qid: str) -> dict:
    data = json.loads(http_get(ENTITY.format(qid)))
    return data["entities"][qid]


def label(ent: dict, lang: str) -> str | None:
    v = ent.get("labels", {}).get(lang)
    return v["value"] if v else None


def aliases(ent: dict, lang: str) -> list[str]:
    return [a["value"] for a in ent.get("aliases", {}).get(lang, [])]


def claim_values(ent: dict, prop: str) -> list:
    out = []
    for c in ent.get("claims", {}).get(prop, []):
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        dv = snak["datavalue"]["value"]
        out.append(dv)
    return out


def entity_ids(ent: dict, prop: str) -> list[str]:
    return [v["id"] for v in claim_values(ent, prop) if isinstance(v, dict) and "id" in v]


def strings(ent: dict, prop: str) -> list[str]:
    return [v for v in claim_values(ent, prop) if isinstance(v, str)]


def report(row: dict) -> None:
    rid, qid = row["id"], row["wikidata_qid"]
    print("\n" + "=" * 78)
    print(f"id {rid}  |  {row['bg_name']}  ({row['taxon']})")
    print(f"  status={row['redbook_status']}  vol={row['redbook_vol']}  qid={qid}")
    print(f"  redbook_url: {row['redbook_url']}")

    # Red Book prose
    try:
        text = redbook_text(row["redbook_url"])
        OUT.mkdir(parents=True, exist_ok=True)
        dest = OUT / f"{rid}.txt"
        dest.write_text(text, encoding="utf-8")
        preview = "\n".join(text.splitlines()[:8])
        print(f"\n  Red Book prose saved -> {dest}  ({len(text)} chars). Read it for the sections.")
        print("  --- preview ---")
        for line in preview.splitlines():
            print(f"  | {line[:100]}")
    except Exception as e:  # noqa: BLE001
        print(f"  !! Red Book fetch failed: {e}")

    # Wikidata facts
    if not qid:
        print("\n  (no QID — Taxobox cannot auto-fill; reconcile/create the item first)")
        return
    try:
        ent = entity(qid)
    except Exception as e:  # noqa: BLE001
        print(f"  !! Wikidata fetch failed: {e}")
        return

    p225 = strings(ent, "P225")
    p105 = entity_ids(ent, "P105")
    p18 = strings(ent, "P18")
    p141 = entity_ids(ent, "P141")
    p935 = strings(ent, "P935")
    parents = entity_ids(ent, "P171")

    print("\n  --- Wikidata ---")
    print(f"  bg label: {label(ent, 'bg')}   en: {label(ent, 'en')}")
    al = aliases(ent, "bg")
    if al:
        print(f"  bg aliases (synonyms): {', '.join(al)}")
    print(f"  P225 scientific name: {', '.join(p225) or '-'}")
    print(f"  P105 rank qids: {', '.join(p105) or '-'}")
    print(f"  P18 image: {p18[0] if p18 else '-'}")
    print(f"  P141 IUCN qids: {', '.join(p141) or '-'}")
    print(f"  P935 Commons cat: {p935[0] if p935 else '-'}")

    if parents:
        print("  P171 parent taxa (resolve the family from these):")
        for pq in parents:
            try:
                pe = entity(pq)
                pname = ", ".join(strings(pe, "P225")) or label(pe, "en") or pq
                rank = entity_ids(pe, "P105")
                print(f"    {pq}  {pname}  bg={label(pe, 'bg')}  rank_qid={','.join(rank) or '-'}")
            except Exception as e:  # noqa: BLE001
                print(f"    {pq}  (lookup failed: {e})")
    else:
        print("  P171 parent taxa: -")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="+", help="tracking.csv ids to gather")
    args = ap.parse_args()

    by_id = {r["id"]: r for r in load_rows()}
    missing = [i for i in args.ids if i not in by_id]
    if missing:
        print(f"Unknown ids: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    for i in args.ids:
        report(by_id[i])


if __name__ == "__main__":
    main()
