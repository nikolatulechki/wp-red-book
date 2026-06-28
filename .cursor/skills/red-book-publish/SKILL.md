---
name: red-book-publish
description: >-
  Create and publish missing bg.wikipedia articles for Red Book (Червена книга)
  species end-to-end: pick truly-missing species, gather Red Book + Wikidata
  sources, write the article wikitext, publish via MediaWiki API, set the
  Wikidata bgwiki sitelink, then update tracking.csv and the bot log. Use when
  asked to create, write, draft, or upload Red Book / Червена книга articles, or
  when working in the red-book project.
---

# Red Book → bg.wikipedia publishing runbook

Operational runbook for the `red-book` project. **Content rules** (skeletons,
status codes, category rules) live in `TEMPLATE.md` — read it before writing
prose. This skill is the *how-to-run-it* layer that stops you re-deriving the
workflow each session.

All commands run from the repo root (`~/Projects/wiki/red-book`) using the
project venv: `. .venv/bin/activate` (or prefix with `.venv/bin/python`).

## Hard-won facts (do NOT rediscover these)

- **Publish path:** `outbox/<Title>.mw` → `scripts/publish_api.py` (MediaWiki API,
  ~seconds per page). Same bot password as wikipedia-git (`BOTulechki@gitBot` via
  git credential helper). `publish.sh` is a thin wrapper around `publish_api.py`.
- **Local clones are API-synced, not git.** `wiki/articles/<Title>.mw` is a local
  mirror refreshed by `scripts/sync_articles.py`; `wiki/articles/.revids.json`
  stores the base revid each copy was synced from. There is **no** git-remote
  clone for articles anymore — the old mega-clone was retired (it re-listed ~360
  pages per push, 1–3 min).
- **Editing existing articles is conflict-safe.** `publish_api.py --allow-existing`
  sends the synced `baserevid`; if the live page moved (e.g. a human edit) the API
  raises an edit conflict and refuses to overwrite (exit 4). Always
  `sync_articles.py` the title first, edit the mirror file, then push.
- `wiki/bot/bot-pages/` stays a small git-remote clone for the bot project log.
- A species is only **truly missing** if its Wikidata QID has **no `bgwiki`
  sitelink** AND the `bg_name` page **does not exist on bgwiki**. `tracking.csv
  wp_exists=no` alone gives false missings (the article may exist under a
  different title, or exist with no Wikidata sitelink). `select_candidates.py`
  enforces both checks.
- **Idempotency (do NOT re-create already-published articles):** three guards,
  all must stay in place. (1) `select_candidates.py` excludes any title that
  already has a WD sitelink or a live bgwiki page. (2) `prepare_brief.py` refuses
  ids whose `content_status != todo` or `wp_exists != no` (use `--force` only to
  override). (3) `publish_api.py` is `createonly` — it **skips** existing pages,
  reconciles `tracking.csv`, and archives published drafts out of `outbox/`.
  `outbox/` must contain **pending drafts only**; published `.mw` move to
  `wiki/articles/`.
- The **Wikidata sitelink is a separate write** (different credential) via
  `wikidata-pybot` with `PYWIKIBOT_DIR=~/Projects/wiki/wikidata-pybot`. The bg
  `{{Taxobox}}` stays empty until this link exists. Handled by
  `scripts/link_wikidata_sitelinks.py`.
- **Categories are NOT a writing step.** Phase B writers add **no categories at
  all** (neither taxonomic nor geographic) — picking/verifying categories was the
  slowest part of Phase B. Categories are added in a separate **batch** pass
  later. No `{{мъниче}}` stub either. (TEMPLATE.md §6a documents the convention
  the batch pass will apply.)

## Model routing (three phases)

Use **Auto/Composer** for prep and shipping; **Opus** only for writing Bulgarian
prose. See `.cursor/rules/red-book-models.mdc` and subagent
`.cursor/agents/red-book-writer.md`.

| Phase | Model | Steps | Stop when |
| --- | --- | --- | --- |
| **A — Prep** | Auto | 1–2 | `drafts/<id>_<Title>/` exists |
| **B — Write** | Opus | 3 | `outbox/<Title>.mw` exists |
| **C — Ship** | Auto | 4–7 | published + logged |

Phase A command (replaces hand-running fetch_sources + ad-hoc notes):

```bash
.venv/bin/python scripts/select_candidates.py --n 5
.venv/bin/python scripts/prepare_brief.py <ids...>
```

Phase B: switch model to Opus, then `/red-book-writer` or ask it to write from
`drafts/.../`. Phase C: switch back to Auto for the checklist below (steps 4–7).

## Workflow — copy this checklist and track it

```
- [ ] 1. Pick candidates:   .venv/bin/python scripts/select_candidates.py --n 10
- [ ] 2. Prepare briefs:   .venv/bin/python scripts/prepare_brief.py <ids...>
- [ ] 3. Write .mw (Opus):  outbox/<Bg_Title>.mw from drafts/ + TEMPLATE.md
- [ ] 4. Pre-flight links:  .venv/bin/python scripts/check_links.py outbox/<Bg_Title>.mw ...
- [ ] 5. Publish to wiki:   scripts/publish_api.py <Bg_Title> ...  (or publish.sh)
- [ ] 6. Wikidata sitelinks:.venv/bin/python scripts/link_wikidata_sitelinks.py --ids <ids...>
- [ ] 7. Verify + record:   update tracking.csv (content_status=published_bot), update bot log
```

### Step 1 — pick candidates
`select_candidates.py` returns rows that are missing AND have a QID with no
`bgwiki` sitelink AND a `redbook_url`. It prints `id  bg_name  taxon  status
vol  qid  redbook_url`. Flags `--group plants_fungi|animals` and `--status CR`
narrow the pool. If it warns that a row is a *false missing*, run
`scripts/sweep_wp_via_wikidata.py` to correct `tracking.csv` first.

### Step 2 — prepare briefs (Phase A)
`prepare_brief.py <ids...>` gathers Red Book prose + Wikidata facts and writes
`drafts/<id>_<Bg_Title>/` with `brief.md`, `redbook.txt`, and
`skeleton.wikitext`. Use this instead of `/tmp/rb/` — briefs survive across
sessions and feed Phase B (Opus).

`fetch_sources.py <ids...>` still works for a quick terminal preview; it saves
to `/tmp/rb/<id>.txt` only.

### Step 3 — write the article
Follow `TEMPLATE.md` exactly. One `.mw` file per species at
`outbox/<Bg_Title_With_Underscores>.mw` (tracked in git). Map Red Book sections → wiki
sections per TEMPLATE.md §2; derive the Bulgarian family name from the `P171`
chain; set `status_bg` from `redbook_status`. **Add no categories** (taxonomic or
geographic) — categories are applied in a separate batch pass later, never
per-article during Phase B.

### Step 4 — pre-flight links
`check_links.py <files...>` reports every `[[link]]` and `[[Категория:…]]` that
does **not** exist on bgwiki, so you fix red links / wrong family-category names
*before* pushing. Re-run until clean.

### Step 5 — publish
`scripts/publish_api.py <Bg_Title> ...` (or `scripts/publish.sh`, same thing)
reads `outbox/<Title>.mw`, logs in via the bot password, creates the page with
`action=edit` (`createonly`), and purges for Taxobox refresh. Override summary
with `PUBLISH_SUMMARY=...`. Pass titles as `.mw` basenames **without** extension.

```bash
.venv/bin/python scripts/publish_api.py --dry-run Винчелистен_лопен   # validate paths
.venv/bin/python scripts/publish_api.py Винчелистен_лопен
```

### Step 6 — Wikidata sitelinks
`link_wikidata_sitelinks.py --ids <ids...>` sets the `bgwiki` sitelink on each
QID (skips any item that already has one — safe to re-run), writes the
`wd_linked` column in `tracking.csv`, and is resumable. Needs the Wikidata bot
credential at `~/Projects/wiki/wikidata-pybot/` (auto-set as `PYWIKIBOT_DIR`).

### Step 7 — verify and record
`publish_api.py` purges each page after create. Confirm the two-way Wikidata link
and that the Taxobox renders family/genus after step 6, then:
- set `content_status=published_bot`, `wp_exists=yes`, `wp_url` on each row in
  `tracking.csv`;
- append each new article as a bullet **at the end** of `== Създадени статии ==`
  on the bot log (`wiki/bot/bot-pages/`) in **creation order** (do **not**
  re-sort the list alphabetically) and push via the small git clone.

## Editing an existing article (conflict-safe)

For follow-ups that touch already-live articles (`LOCAL_NOTES.md`: taxobox Red
Book line, Latin redirects), never blind-overwrite. Sync → edit → push:

```bash
.venv/bin/python scripts/sync_articles.py --titles "Алепска млечка"   # pull live wikitext + revid
# edit wiki/articles/Алепска_млечка.mw locally
.venv/bin/python scripts/publish_api.py --allow-existing --summary "…" Алепска_млечка
```

`sync_articles.py --check` reports drift (local vs live revid) without writing.
A push that hits an edit conflict exits 4 — re-sync that title and re-apply.

## Recovery & details

See [reference.md](reference.md) for legacy git-remote-mediawiki notes (bot log
clone only), credential/keychain fixes, the windows-1251 Red Book gotchas, and
shell pitfalls (BSD vs GNU, `&&` on grep exit 1, sticky shell cwd).
