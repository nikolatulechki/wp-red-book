#!/usr/bin/env python3
"""Add Bulgarian Red Book P14254 statements for manually matched taxa.

Reads a manual-matches CSV (default ``wikidata-modelling/new_matches.csv``) for
Wikidata Q-ids and joins ``tracking.csv`` for ``redbook_status`` / ``redbook_url``.
Skips items that already carry an identical P14254 statement (same status + P3680
qualifier).

Auth: Wikidata bot at ~/Projects/wiki/wikidata-pybot/ (see link_wikidata_sitelinks.py).

Usage:
    python scripts/add_redbook_wikidata_status.py --dry-run
    python scripts/add_redbook_wikidata_status.py
    python scripts/add_redbook_wikidata_status.py --matches wikidata-modelling/more_new_matches.csv
    python scripts/add_redbook_wikidata_status.py --from-tsv wikidata-modelling/new_matches_quickstatements.tsv
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
NEW_MATCHES = REPO / "wikidata-modelling" / "new_matches.csv"

STATUS = {
    "CR": "Q219127",
    "EN": "Q96377276",
    "VU": "Q278113",
    "RE": "Q10594853",
    "EX": "Q237350",
}
RED_BOOK = "Q12299068"  # online e-ecodb edition (matches quickstatements.tsv)
BULGARIA = "Q219"

QS_LINE = re.compile(
    r'^(?P<qid>Q\d+)\tP14254\t(?P<status>Q\d+)\t'
    r'P1001\tQ219\tP3680\t(?P<redbook>Q\d+)\t'
    r'S248\t(?P=redbook)\tS854\t"(?P<url>[^"]+)"\t'
    r'S813\t\+(?P<retrieved>\d{4}-\d{2}-\d{2})T00:00:00Z/11$'
)


def load_from_csv(matches_path: Path) -> list[dict]:
    from common import load_rows

    tracking = {r["id"]: r for r in load_rows()}
    rows: list[dict] = []
    with matches_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rid = row["id"]
            tr = tracking.get(rid)
            if not tr:
                raise SystemExit(f"tracking.csv has no row for id {rid}")
            code = tr["redbook_status"].strip()
            status_qid = STATUS.get(code)
            if not status_qid:
                raise SystemExit(f"id {rid}: unknown redbook_status {code!r}")
            rows.append(
                {
                    "id": rid,
                    "qid": row["wikidata_qid"].strip(),
                    "status_code": code,
                    "status_qid": status_qid,
                    "url": row.get("redbook_url", tr["redbook_url"]).strip(),
                    "taxon": row.get("rb_taxon", tr["taxon"]).strip(),
                }
            )
    return rows


def load_from_tsv(path: Path) -> list[dict]:
    rows: list[dict] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        m = QS_LINE.match(line)
        if not m:
            raise SystemExit(f"{path}:{lineno}: cannot parse QuickStatements line")
        status_qid = m.group("status")
        code = next((k for k, v in STATUS.items() if v == status_qid), status_qid)
        rows.append(
            {
                "id": str(lineno),
                "qid": m.group("qid"),
                "status_code": code,
                "status_qid": status_qid,
                "url": m.group("url"),
                "taxon": m.group("qid"),
            }
        )
    return rows


def has_redbook_statement(item, status_qid: str, red_book_qid: str = RED_BOOK) -> bool:
    for claim in item.claims.get("P14254", []):
        target = claim.getTarget()
        if not hasattr(target, "id") or target.id != status_qid:
            continue
        for qual in claim.qualifiers.get("P3680", []):
            qtarget = qual.getTarget()
            if hasattr(qtarget, "id") and qtarget.id == red_book_qid:
                return True
    return False


def add_statement(repo, item, status_qid: str, url: str, retrieved: str) -> None:
    import pywikibot
    from pywikibot import Claim, ItemPage, WbTime

    claim = Claim(repo, "P14254")
    claim.setTarget(ItemPage(repo, status_qid))

    q_jurisdiction = Claim(repo, "P1001")
    q_jurisdiction.setTarget(ItemPage(repo, BULGARIA))
    claim.addQualifier(q_jurisdiction)

    q_supported = Claim(repo, "P3680")
    q_supported.setTarget(ItemPage(repo, RED_BOOK))
    claim.addQualifier(q_supported)

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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--matches",
        type=Path,
        default=NEW_MATCHES,
        help="manual-matches CSV with wikidata_qid + id (default: new_matches.csv)",
    )
    ap.add_argument(
        "--from-tsv",
        type=Path,
        help="apply lines from a QuickStatements TSV instead of a matches CSV",
    )
    ap.add_argument("--dry-run", action="store_true", help="show planned edits only")
    args = ap.parse_args()

    if args.from_tsv:
        rows = load_from_tsv(args.from_tsv)
    else:
        rows = load_from_csv(args.matches)
    if not rows:
        print("Nothing to do.")
        return

    retrieved = date.today().isoformat()
    print(f"{len(rows)} statement(s) to add (retrieved {retrieved}):")
    for r in rows:
        print(
            f"  id {r['id']:>3}  {r['qid']:<11}  {r['status_code']:>2}  {r['taxon']}"
        )

    if args.dry_run:
        print("\n--dry-run: no changes made.")
        return

    from wikidata_pybot import delay, get_item, get_repo

    repo = get_repo()
    added = skipped = failed = 0

    for r in rows:
        rid, qid = r["id"], r["qid"]
        try:
            item = get_item(repo, qid)
            item.get()
            if has_redbook_statement(item, r["status_qid"]):
                print(f"  id {rid}: {qid} already has P14254 ({r['status_code']}); skip")
                skipped += 1
                continue
            add_statement(repo, item, r["status_qid"], r["url"], retrieved)
            print(f"  id {rid}: added P14254 {r['status_code']} on {qid}")
            added += 1
            delay(1)
        except Exception as e:  # noqa: BLE001
            print(f"  id {rid}: FAILED {qid} ({e})")
            failed += 1

    print(f"\nDone. added={added}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
