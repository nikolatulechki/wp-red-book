#!/usr/bin/env python3
"""Create Wikidata taxon items for Red Book taxa with no Wikidata match.

Reads ``wikidata-modelling/new_items_to_create.csv`` (taxa flagged
"NEW ITEM TO CREATE") and creates a minimal but correct taxon item for each:

  P31    instance of                   = taxon (Q16521)
  P225   taxon name                    = scientific name (string)
  P105   taxonomic rank                = species / subspecies / variety
  P171   parent taxon                  = resolved species (for subsp.) or genus
  P1843  taxon common name             = Bulgarian Red Book vernacular (bg)
  P14254 regional conservation status  = Bulgarian Red Book category
           + P1001 Bulgaria (Q219)
           + P3680 Red Book online edition (Q12299068)
           + reference P248 / P854 (e-ecodb URL) / P813 (retrieved)

Safety:
  - reconcile-before-create: skips when an item already carries the exact
    scientific name in P225 (SPARQL exact match);
  - --dry-run prints the plan (resolved parents, ranks, dedup) with no writes;
  - rate-limited; writes the new QID back to the input CSV and tracking.csv
    after each create (resumable).

Auth: Wikidata bot at ~/Projects/wiki/wikidata-pybot/ (PYWIKIBOT_DIR auto-set).

Usage:
    python scripts/create_new_items.py --dry-run
    python scripts/create_new_items.py
    python scripts/create_new_items.py --ids 18 271
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from datetime import date
from pathlib import Path

PYBOT_DIR = Path.home() / "Projects" / "wiki" / "wikidata-pybot"
os.environ.setdefault("PYWIKIBOT_DIR", str(PYBOT_DIR))

REPO = Path(__file__).resolve().parent.parent
NEW_ITEMS = REPO / "wikidata-modelling" / "new_items_to_create.csv"

from common import add_note, load_rows, save_rows  # noqa: E402

TAXON = "Q16521"
RED_BOOK = "Q12299068"  # online e-ecodb edition (matches quickstatements.tsv)
BULGARIA = "Q219"

STATUS = {
    "CR": "Q219127",
    "EN": "Q96377276",
    "VU": "Q278113",
    "RE": "Q10594853",
    "EX": "Q237350",
}

RANK = {
    "species": "Q7432",
    "subspecies": "Q68947",
    "variety": "Q767728",
    "form": "Q279749",
    "genus": "Q34740",
}

# Bulgarian Red Book taxon group -> (en kingdom word, bg kingdom word).
KINGDOM = {
    "plants_fungi": ("plant", "растение"),
    "animals": ("insect", "насекомо"),  # both animal rows here are insects
}
RANK_BG = {"species": "вид", "subspecies": "подвид", "variety": "вариетет", "form": "форма"}

# Verified parent QIDs that override CSV/SPARQL resolution.
#  18 : CSV-provided Q164539 (Hornungia alpina = Pritzelago alpina), correct.
# 638 : CSV value Q1017262 is WRONG (that is Caragana frutex); genus Hieracium is Q16526.
PARENT_OVERRIDE = {"18": "Q164539", "638": "Q16526"}


def parse_taxon(name: str) -> tuple[str, str | None]:
    """Return (rank_key, parent_name) parsed from a scientific name string."""
    name = re.sub(r"\s+", " ", name).strip()
    for marker, rank in (("subsp.", "subspecies"), ("var.", "variety"), ("f.", "form")):
        sep = f" {marker} "
        if sep in name:
            return rank, name.split(sep, 1)[0].strip()
    parts = name.split()
    if len(parts) >= 2:
        return "species", parts[0]  # parent = genus
    return "genus", None


def _sparql_taxa_by_name(name: str) -> list[dict]:
    from wikidata_pybot import binding_value, execute_query, qid_from_uri

    safe = name.replace("\\", "\\\\").replace('"', '\\"')
    query = (
        "SELECT ?item ?rank WHERE { "
        f'?item wdt:P225 "{safe}" . '
        "OPTIONAL { ?item wdt:P105 ?rank . } } LIMIT 20"
    )
    out: dict[str, set] = {}
    for b in execute_query(query):
        qid = qid_from_uri(binding_value(b, "item"))
        rank = qid_from_uri(binding_value(b, "rank"))
        if qid:
            out.setdefault(qid, set())
            if rank:
                out[qid].add(rank)
    return [{"qid": q, "ranks": r} for q, r in out.items()]


def find_existing(sci_name: str) -> list[str]:
    """QIDs already carrying this exact scientific name in P225."""
    return [m["qid"] for m in _sparql_taxa_by_name(sci_name)]


def resolve_parent(parent_name: str, expected_rank_qid: str) -> tuple[str | None, str]:
    matches = _sparql_taxa_by_name(parent_name)
    if not matches:
        return None, f"no P225 match for {parent_name!r}"
    ranked = [m["qid"] for m in matches if expected_rank_qid in m["ranks"]]
    if len(ranked) == 1:
        return ranked[0], "ok"
    if len(ranked) > 1:
        return ranked[0], f"{len(ranked)} rank-matched; picked {ranked[0]}"
    if len(matches) == 1:
        return matches[0]["qid"], "single match (rank unset)"
    qids = [m["qid"] for m in matches]
    return None, f"ambiguous {qids}"


def build_rows(args: argparse.Namespace) -> list[dict]:
    tracking = {r["id"]: r for r in load_rows()}
    wanted = set(args.ids) if args.ids else None
    rows: list[dict] = []
    with NEW_ITEMS.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rid = (row.get("id") or "").strip()
            if not rid or (wanted and rid not in wanted):
                continue
            tr = tracking.get(rid)
            if not tr:
                raise SystemExit(f"tracking.csv has no row for id {rid}")
            sci = (row.get("rb_taxon") or tr["rb_taxon"] or tr["taxon"]).strip()
            code = tr["redbook_status"].strip()
            if code not in STATUS:
                raise SystemExit(f"id {rid}: unknown redbook_status {code!r}")
            rank_key, parent_name = parse_taxon(sci)
            rows.append(
                {
                    "id": rid,
                    "raw": row,
                    "sci": sci,
                    "vernacular": (row.get("rb_bg_name") or tr["rb_bg_name"]).strip(),
                    "url": (row.get("redbook_url") or tr["redbook_url"]).strip(),
                    "group": tr["group"].strip(),
                    "status_code": code,
                    "status_qid": STATUS[code],
                    "rank_key": rank_key,
                    "parent_csv": (row.get("parent") or "").strip(),
                    "parent_name": parent_name,
                }
            )
    return rows, fieldnames


def descriptions(group: str, rank_key: str) -> dict[str, str]:
    en_word, bg_word = KINGDOM.get(group, ("organism", "организъм"))
    rank_en = {"species": "species", "subspecies": "subspecies", "variety": "variety",
               "form": "form", "genus": "genus"}[rank_key]
    return {
        "en": f"{rank_en} of {en_word}",
        "bg": f"{RANK_BG.get(rank_key, rank_key)} {bg_word}",
    }


def add_redbook_status(repo, item, status_qid: str, url: str, retrieved: str) -> None:
    from pywikibot import Claim, ItemPage, WbTime

    claim = Claim(repo, "P14254")
    claim.setTarget(ItemPage(repo, status_qid))

    q_jur = Claim(repo, "P1001")
    q_jur.setTarget(ItemPage(repo, BULGARIA))
    claim.addQualifier(q_jur)
    q_sup = Claim(repo, "P3680")
    q_sup.setTarget(ItemPage(repo, RED_BOOK))
    claim.addQualifier(q_sup)

    s_stated = Claim(repo, "P248")
    s_stated.setTarget(ItemPage(repo, RED_BOOK))
    s_url = Claim(repo, "P854")
    s_url.setTarget(url)
    s_date = Claim(repo, "P813")
    y, m, d = (int(x) for x in retrieved.split("-"))
    s_date.setTarget(WbTime(year=y, month=m, day=d, precision=11, site=repo))
    claim.addSources([s_stated, s_url, s_date])

    item.addClaim(
        claim,
        summary="bot: add Bulgarian Red Book regional conservation status (P14254)",
    )


def writeback_csv(fieldnames: list[str], rid: str, qid: str) -> None:
    with NEW_ITEMS.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if (r.get("id") or "").strip() == rid:
            r["wikidata_qid"] = qid
    with NEW_ITEMS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def writeback_tracking(rid: str, qid: str) -> None:
    rows = load_rows()
    for r in rows:
        if r["id"] == rid:
            r["wikidata_qid"] = qid
            add_note(r, "wikidata item created by bot")
    save_rows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", nargs="*", help="restrict to these tracking ids")
    ap.add_argument("--dry-run", action="store_true", help="resolve + print plan, no writes")
    args = ap.parse_args()

    rows, fieldnames = build_rows(args)
    if not rows:
        print("Nothing to create.")
        return

    retrieved = date.today().isoformat()
    from wikidata_pybot import delay

    print(f"Planning {len(rows)} item(s) (retrieved {retrieved}):\n")
    plan: list[dict] = []
    for r in rows:
        existing = find_existing(r["sci"])
        if existing:
            r["skip"] = f"already exists: {existing}"
            print(f"  id {r['id']:>3}  SKIP  {r['sci']}  -> {existing}")
            plan.append(r)
            continue

        expected_parent_rank = RANK["species"] if r["rank_key"] != "species" else RANK["genus"]
        if r["id"] in PARENT_OVERRIDE:
            parent_qid, why = PARENT_OVERRIDE[r["id"]], "verified override"
        elif r["parent_csv"].startswith("Q"):
            parent_qid, why = r["parent_csv"], "from CSV"
        elif r["parent_name"]:
            parent_qid, why = resolve_parent(r["parent_name"], expected_parent_rank)
        else:
            parent_qid, why = None, "no parent name"
        r["parent_qid"] = parent_qid
        desc = descriptions(r["group"], r["rank_key"])
        r["desc"] = desc
        print(
            f"  id {r['id']:>3}  {r['rank_key']:<10} {r['sci']}\n"
            f"          bg='{r['vernacular']}'  P171={parent_qid or '-'} ({why})  "
            f"P14254={r['status_code']}  desc.en='{desc['en']}'"
        )
        plan.append(r)

    if args.dry_run:
        print("\n--dry-run: no changes made.")
        return

    import pywikibot

    from wikidata_pybot import add_claim, create_item, get_repo, set_label

    repo = get_repo()
    created = skipped = failed = 0

    for r in plan:
        rid, sci = r["id"], r["sci"]
        if r.get("skip"):
            skipped += 1
            continue
        try:
            labels = {"mul": sci}
            if r["vernacular"] and r["vernacular"] != sci:
                labels["bg"] = r["vernacular"]
            item = create_item(
                repo,
                labels=labels,
                descriptions=r["desc"],
                summary=f"bot: create Red Book taxon item ({sci})",
            )
            qid = item.title()
            add_claim(item, "P31", TAXON, summary="bot: instance of taxon")
            add_claim(item, "P225", sci, summary="bot: taxon name")
            add_claim(item, "P105", RANK[r["rank_key"]], summary="bot: taxonomic rank")
            if r["parent_qid"]:
                add_claim(item, "P171", r["parent_qid"], summary="bot: parent taxon")
            if r["vernacular"] and r["vernacular"] != sci:
                add_claim(
                    item,
                    "P1843",
                    pywikibot.WbMonolingualText(text=r["vernacular"], language="bg"),
                    summary="bot: Bulgarian taxon common name",
                )
            add_redbook_status(repo, item, r["status_qid"], r["url"], retrieved)

            writeback_csv(fieldnames, rid, qid)
            writeback_tracking(rid, qid)
            print(f"  id {rid}: created {qid}  {sci}")
            created += 1
            delay(1)
        except Exception as e:  # noqa: BLE001
            print(f"  id {rid}: FAILED {sci} ({e})")
            failed += 1

    print(f"\nDone. created={created}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
