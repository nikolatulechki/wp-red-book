#!/usr/bin/env python3
"""Prepare writer briefs for Phase A of the red-book publish workflow.

For each tracking id, downloads Red Book prose + Wikidata facts and writes a
self-contained folder under drafts/ for the Opus writing phase:

    drafts/<id>_<Bg_Title>/
        brief.md          structured facts + section map hints
        redbook.txt       full Red Book entry (utf-8)
        skeleton.wikitext Taxobox + empty sections pre-filled

Usage:
    python scripts/prepare_brief.py 11 12
    python scripts/prepare_brief.py --ids-from-candidates --n 3
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from common import REPO, load_rows
from fetch_sources import (
    aliases,
    entity,
    entity_ids,
    label,
    redbook_text,
    strings,
)

DRAFTS = REPO / "drafts"

# Wikidata taxon ranks (subset used for family/genus hints)
# (species=Q7432, genus=Q34740, family=Q35409)
RANK_FAMILY = "Q35409"
RANK_GENUS = "Q34740"

# Red Book section headers → wiki section (from TEMPLATE.md §2)
SECTION_MARKERS = [
    ("Морфология и биология", "== Описание =="),
    ("Местообитания и популации", "== Местообитания == / == Численост =="),
    ("Разпространение в България", "== Разпространение == (Bulgaria)"),
    ("Общо разпространение", "== Разпространение == (world) — use for endemic §6a"),
    ("Отрицателно действащи фактори", "== Заплахи =="),
    ("Предприети мерки", "== Мерки за защита =="),
    ("Необходими мерки", "== Мерки за защита =="),
    ("Биология", "== Начин на живот =="),
    ("Размножаване", "== Размножаване =="),
    ("Природозащитен статут", "lead + Taxobox status_bg"),
]

BG_MONTHS = {
    1: "януари",
    2: "февруари",
    3: "март",
    4: "април",
    5: "май",
    6: "юни",
    7: "юли",
    8: "август",
    9: "септември",
    10: "октомври",
    11: "ноември",
    12: "декември",
}


def title_to_dirname(bg_name: str) -> str:
    return bg_name.replace(" ", "_")


def draft_dir(row: dict) -> Path:
    return DRAFTS / f"{row['id']}_{title_to_dirname(row['bg_name'])}"


def bg_date(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.day} {BG_MONTHS[d.month]} {d.year} г."


def extract_section(text: str, header: str, max_chars: int = 2000) -> str | None:
    """Return text under a Red Book section header until the next known header.

    Red Book headers sit at the start of a line and are followed by ``. <text>``
    on the *same* line (e.g. ``Морфология и биология. Едногодишно ...``), so the
    body capture starts right after the header, optionally past a leading dot.
    """
    others = "|".join(re.escape(h) for h, _ in SECTION_MARKERS if h != header)
    pattern = re.compile(
        rf"(?ims)^\s*{re.escape(header)}\s*\.?\s*(.*?)(?=\n\s*(?:{others})[\s.]|\Z)",
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return None
    body = m.group(1).strip()
    return body[:max_chars] + ("…" if len(body) > max_chars else "")


def list_present_sections(text: str) -> list[tuple[str, str]]:
    present = []
    for rb_header, wiki_target in SECTION_MARKERS:
        if re.search(rf"(?im)^\s*{re.escape(rb_header)}[\s.]", text):
            present.append((rb_header, wiki_target))
    return present


def resolve_parents(qid: str) -> list[dict]:
    """Walk P171 chain; return parent entries with labels and ranks."""
    out: list[dict] = []
    try:
        ent = entity(qid)
    except Exception:  # noqa: BLE001
        return out
    for pq in entity_ids(ent, "P171"):
        try:
            pe = entity(pq)
            ranks = entity_ids(pe, "P105")
            out.append(
                {
                    "qid": pq,
                    "scientific": ", ".join(strings(pe, "P225")) or label(pe, "en") or pq,
                    "bg": label(pe, "bg"),
                    "rank_qids": ranks,
                }
            )
        except Exception:  # noqa: BLE001
            out.append({"qid": pq, "scientific": pq, "bg": None, "rank_qids": []})
    return out


def family_and_genus(parents: list[dict]) -> tuple[dict | None, dict | None]:
    family = genus = None
    for p in parents:
        ranks = set(p.get("rank_qids") or [])
        if RANK_FAMILY in ranks and family is None:
            family = p
        if RANK_GENUS in ranks and genus is None:
            genus = p
    return family, genus


def wikidata_block(row: dict) -> dict:
    qid = row["wikidata_qid"].strip()
    if not qid:
        return {"error": "no QID — reconcile or create Wikidata item first"}
    ent = entity(qid)
    parents = resolve_parents(qid)
    family, genus = family_and_genus(parents)
    return {
        "qid": qid,
        "bg_label": label(ent, "bg"),
        "en_label": label(ent, "en"),
        "bg_aliases": aliases(ent, "bg"),
        "p225": strings(ent, "P225"),
        "p105_rank_qids": entity_ids(ent, "P105"),
        "p18_image": strings(ent, "P18")[:1],
        "p141_iucn_qids": entity_ids(ent, "P141"),
        "p935_commons": strings(ent, "P935")[:1],
        "parents": parents,
        "family_hint": family,
        "genus_hint": genus,
    }


def build_brief_md(row: dict, wd: dict, rb_text: str) -> str:
    downloaded = bg_date()
    world_dist = extract_section(rb_text, "Общо разпространение")
    bg_dist = extract_section(rb_text, "Разпространение в България")
    sections = list_present_sections(rb_text)

    lines = [
        f"# Writer brief: {row['bg_name']}",
        "",
        "Phase B (Opus): write `outbox/"
        f"{title_to_dirname(row['bg_name'])}.mw` from this brief, "
        "`redbook.txt`, and `skeleton.wikitext`. Follow `TEMPLATE.md`.",
        "",
        "## Tracking row",
        "",
        f"| Field | Value |",
        f"| --- | --- |",
        f"| id | {row['id']} |",
        f"| bg_name (page title) | {row['bg_name']} |",
        f"| taxon | {row['taxon']} |",
        f"| group | {row['group']} |",
        f"| redbook_vol | {row['redbook_vol']} |",
        f"| redbook_status | {row['redbook_status']} |",
        f"| redbook_url | {row['redbook_url']} |",
        f"| wikidata_qid | {row['wikidata_qid']} |",
        f"| downloaded (for ref) | {downloaded} |",
        "",
    ]

    if "error" in wd:
        lines.extend(["## Wikidata", "", f"**{wd['error']}**", ""])
    else:
        lines.extend(
            [
                "## Wikidata",
                "",
                f"- bg label: {wd.get('bg_label') or '—'}",
                f"- en label: {wd.get('en_label') or '—'}",
            ]
        )
        if wd.get("bg_aliases"):
            lines.append(f"- bg aliases: {', '.join(wd['bg_aliases'])}")
        lines.extend(
            [
                f"- P225: {', '.join(wd.get('p225') or []) or '—'}",
                f"- P18 image: {wd['p18_image'][0] if wd.get('p18_image') else '—'}",
                f"- P141 IUCN qids: {', '.join(wd.get('p141_iucn_qids') or []) or '—'}",
                f"- P935 Commons: {wd['p935_commons'][0] if wd.get('p935_commons') else '—'}",
                "",
                "### P171 parent chain",
                "",
            ]
        )
        for p in wd.get("parents") or []:
            lines.append(
                f"- {p['qid']} `{p['scientific']}` bg={p.get('bg') or '—'} "
                f"rank={','.join(p.get('rank_qids') or []) or '—'}"
            )
        fh = wd.get("family_hint")
        gh = wd.get("genus_hint")
        lines.extend(
            [
                "",
                "### Taxonomy hints (verify on bgwiki before categorizing)",
                "",
                f"- family (P171 rank {RANK_FAMILY}): {fh.get('bg') or fh.get('scientific') if fh else '—'}",
                f"- genus (P171 rank {RANK_GENUS}): {gh.get('bg') or gh.get('scientific') if gh else '—'}",
                "- taxonomic category: deepest level only (genus preferred, else family) — TEMPLATE.md §6a",
                "",
            ]
        )

    lines.extend(
        [
            "## Category decision (§6a — Opus must confirm)",
            "",
            "Geographic category rules:",
            "- Endemic to Bulgaria only → `Флора/Фауна на България`",
            "- Occurs outside Bulgaria → **no** country category (common case)",
            "",
        ]
    )
    if world_dist:
        lines.extend(
            [
                "### Общо разпространение (excerpt)",
                "",
                world_dist,
                "",
            ]
        )
    if bg_dist:
        lines.extend(
            [
                "### Разпространение в България (excerpt)",
                "",
                bg_dist,
                "",
            ]
        )

    lines.extend(
        [
            "## Red Book sections present → wiki mapping",
            "",
        ]
    )
    if sections:
        for rb_h, wiki_h in sections:
            lines.append(f"- `{rb_h}` → {wiki_h}")
    else:
        lines.append("- (no standard headers detected — read `redbook.txt` in full)")

    lines.extend(
        [
            "",
            "## Article output",
            "",
            f"- Target file: `outbox/{title_to_dirname(row['bg_name'])}.mw`",
            f"- Skeleton: `skeleton.wikitext` in this folder",
            "- Full prose source: `redbook.txt`",
            "",
        ]
    )
    return "\n".join(lines)


def build_skeleton(row: dict) -> str:
    downloaded = bg_date()
    status = row["redbook_status"]
    url = row["redbook_url"]
    is_animal = row["group"] == "animals"
    extinct_line = ""
    if status == "EX":
        extinct_line = "\n| status_bg_extinct = «year from Red Book»"

    taxobox = f"""{{{{Taxobox
| status_bg     = {status}
| status_bg_ref = <ref name="ЧК">{{{{Червена книга | title = {{{{PAGENAME}}}} | redbooklink = {url} | downloaded = {downloaded}}}}}</ref>{extinct_line}
}}}}"""

    if is_animal:
        body = f"""{taxobox}

'''«{row['bg_name']}»''' (''{row['taxon']}'') е [[вид (биология)|вид]] «life form» от семейство [[«Family bg»]].<ref name="ЧК"/>

== Описание ==
«from Red Book: Морфология/Биология»<ref name="ЧК"/>

== Разпространение и местообитание ==
«from Red Book»<ref name="ЧК"/>

== Начин на живот и хранене ==
«from Red Book if present»<ref name="ЧК"/>

== Размножаване ==
«from Red Book if present»<ref name="ЧК"/>

== Численост и природозащитен статут ==
«from Red Book»<ref name="ЧК"/>

== Източници ==
<references />

{{{{Нормативен контрол}}}}

[[Категория:«deepest taxonomic — genus or family»]]
"""
    else:
        kingdom = "гъба" if "fungi" in row.get("notes", "").lower() else "растение"
        body = f"""{taxobox}

'''«{row['bg_name']}»''' (''{row['taxon']}'') е «life form» [[{kingdom}]] от семейство [[«Family bg»]].<ref name="ЧК"/>

== Описание ==
«from Red Book: Морфология и биология»<ref name="ЧК"/>

== Разпространение и местообитания ==
«from Red Book»<ref name="ЧК"/>

== Природозащитен статут ==
«from Red Book: threats + measures»<ref name="ЧК"/>

== Източници ==
<references />

{{{{Нормативен контрол}}}}

[[Категория:«deepest taxonomic — genus or family»]]
"""
    return body


def prepare_one(row: dict) -> Path:
    out_dir = draft_dir(row)
    out_dir.mkdir(parents=True, exist_ok=True)

    rb_text = redbook_text(row["redbook_url"])
    (out_dir / "redbook.txt").write_text(rb_text, encoding="utf-8")

    try:
        wd = wikidata_block(row)
    except Exception as e:  # noqa: BLE001
        wd = {"error": str(e)}

    (out_dir / "brief.md").write_text(build_brief_md(row, wd, rb_text), encoding="utf-8")
    (out_dir / "skeleton.wikitext").write_text(build_skeleton(row), encoding="utf-8")
    return out_dir


def pick_candidate_ids(n: int, group: str | None, status: str | None) -> list[str]:
    """Reuse select_candidates filters; return ids only (no live sitelink check)."""
    rows = load_rows()
    pool = [
        r
        for r in rows
        if r.get("content_status", "todo") == "todo"
        and r["wp_exists"] == "no"
        and r["wikidata_qid"].strip()
        and r["redbook_url"].strip()
    ]
    if group:
        pool = [r for r in pool if r["group"] == group]
    if status:
        pool = [r for r in pool if r["redbook_status"] == status.upper()]
    pool.sort(key=lambda r: int(r["id"]))
    return [r["id"] for r in pool[:n]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", help="tracking.csv ids")
    ap.add_argument(
        "--ids-from-candidates",
        action="store_true",
        help="pick ids from tracking filters (run select_candidates.py first for sitelink check)",
    )
    ap.add_argument("--n", type=int, default=3, help="with --ids-from-candidates")
    ap.add_argument("--group", choices=["plants_fungi", "animals"])
    ap.add_argument("--status", help="CR/EN/VU/RE/EX")
    ap.add_argument(
        "--force",
        action="store_true",
        help="brief even ids that are already published/exist (default: refuse them)",
    )
    args = ap.parse_args()

    if args.ids_from_candidates:
        ids = pick_candidate_ids(args.n, args.group, args.status)
        if not ids:
            print("No rows match filters.", file=sys.stderr)
            sys.exit(1)
        print(f"Picking ids from tracking (local filters only): {', '.join(ids)}")
        print("Tip: run select_candidates.py first to verify no false missings.")
    else:
        ids = args.ids
        if not ids:
            ap.print_help()
            sys.exit(1)

    by_id = {r["id"]: r for r in load_rows()}
    missing = [i for i in ids if i not in by_id]
    if missing:
        print(f"Unknown ids: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # Idempotency guard: explicit ids bypass the candidate filters, so refuse
    # any id that we already published / that already has a live article. This
    # is what stops already-created species leaking back into drafts/ + outbox/.
    already_done = [
        i
        for i in ids
        if by_id[i].get("content_status", "todo") != "todo"
        or by_id[i].get("wp_exists", "no") != "no"
    ]
    if already_done and not args.force:
        print(
            "Refusing already-published/existing ids (use --force to override):",
            file=sys.stderr,
        )
        for i in already_done:
            r = by_id[i]
            print(
                f"  id {i}  {r['bg_name']}  "
                f"(content_status={r.get('content_status')}, wp_exists={r.get('wp_exists')})",
                file=sys.stderr,
            )
        ids = [i for i in ids if i not in set(already_done)]
        if not ids:
            print("Nothing left to brief.", file=sys.stderr)
            sys.exit(1)

    for i in ids:
        row = by_id[i]
        try:
            path = prepare_one(row)
            print(f"id {i}  {row['bg_name']}  ->  {path.relative_to(REPO)}/")
        except Exception as e:  # noqa: BLE001
            print(f"id {i}  FAILED: {e}", file=sys.stderr)
            sys.exit(1)

    print("\nPhase A complete. Switch to Opus and run /red-book-writer or Phase B prompt.")


if __name__ == "__main__":
    main()
