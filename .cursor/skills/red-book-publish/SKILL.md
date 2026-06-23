---
name: red-book-publish
description: >-
  Create and publish missing bg.wikipedia articles for Red Book (Червена книга)
  species end-to-end: pick truly-missing species, gather Red Book + Wikidata
  sources, write the article wikitext, push via git-remote-mediawiki, set the
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

- `wiki/articles/` is **one authenticated** `git-remote-mediawiki` clone
  (`BOTulechki@gitBot`). Auth is mandatory — anonymous bulk ops get HTTP 429.
- `git push` to the wiki **always rejects non-fast-forward first**. The fix is
  pull/rebase then push. `git pull --rebase` sometimes fails *"Cannot rebase
  onto multiple branches"* → fall back to `git rebase origin/master`. All of
  this is handled by `scripts/publish.sh`.
- pull/push **re-lists all ~360 tracked pages and is slow (1–3 min). It is NOT
  hung.** Never `pkill` it.
- A species is only **truly missing** if its Wikidata QID has **no `bgwiki`
  sitelink**. `tracking.csv wp_exists=no` alone gives false missings (the article
  may exist under a different title). `select_candidates.py` enforces this.
- The **Wikidata sitelink is a separate write** (different credential) via
  `wikidata-pybot` with `PYWIKIBOT_DIR=~/Projects/wiki/wikidata-pybot`. The bg
  `{{Taxobox}}` stays empty until this link exists. Handled by
  `scripts/link_wikidata_sitelinks.py`.
- Current category convention (TEMPLATE.md §6a): taxonomic = **deepest level
  only** (never also the parent); geographic = `Флора/Фауна на България` **only
  if endemic to Bulgaria**, otherwise add nothing. No `{{мъниче}}` stub.

## Workflow — copy this checklist and track it

```
- [ ] 1. Pick candidates:   .venv/bin/python scripts/select_candidates.py --n 10
- [ ] 2. Gather sources:    .venv/bin/python scripts/fetch_sources.py <ids...>
- [ ] 3. Write .mw files into wiki/articles/<Bg_Title>.mw from TEMPLATE.md skeleton
- [ ] 4. Pre-flight links:  .venv/bin/python scripts/check_links.py wiki/articles/<Bg_Title>.mw ...
- [ ] 5. Publish to wiki:   scripts/publish.sh <Bg_Title> ...
- [ ] 6. Wikidata sitelinks:.venv/bin/python scripts/link_wikidata_sitelinks.py --ids <ids...>
- [ ] 7. Verify + record:   purge pages, update tracking.csv (content_status=published_bot), update bot log
```

### Step 1 — pick candidates
`select_candidates.py` returns rows that are missing AND have a QID with no
`bgwiki` sitelink AND a `redbook_url`. It prints `id  bg_name  taxon  status
vol  qid  redbook_url`. Flags `--group plants_fungi|animals` and `--status CR`
narrow the pool. If it warns that a row is a *false missing*, run
`scripts/sweep_wp_via_wikidata.py` to correct `tracking.csv` first.

### Step 2 — gather sources
`fetch_sources.py <ids...>` decodes each Red Book page (windows-1251) to
`/tmp/rb/<id>.txt` and prints the Wikidata facts you need: `P225` (Latin name),
`P171` parents (→ family; their bg labels + ranks are printed), `P105` rank,
`P18` image, `P141` IUCN, bg aliases. Read `/tmp/rb/<id>.txt` for the prose.

### Step 3 — write the article
Follow `TEMPLATE.md` exactly. One `.mw` file per species at
`wiki/articles/<Bg_Title_With_Underscores>.mw`. Map Red Book sections → wiki
sections per TEMPLATE.md §2; derive the Bulgarian family name from the `P171`
chain; set `status_bg` from `redbook_status`; pick the deepest taxonomic
category that exists on bgwiki; add a geographic category **only** for Bulgarian
endemics.

### Step 4 — pre-flight links
`check_links.py <files...>` reports every `[[link]]` and `[[Категория:…]]` that
does **not** exist on bgwiki, so you fix red links / wrong family-category names
*before* pushing. Re-run until clean.

### Step 5 — publish
`scripts/publish.sh <Bg_Title> ...` registers each page in
`remote.origin.pages`, commits with a Bulgarian edit summary
(`PUBLISH_SUMMARY=...` to override), pulls/rebases, and pushes — with the
non-fast-forward and ref-lock recoveries baked in. Pass titles as the `.mw`
basenames **without** the extension.

### Step 6 — Wikidata sitelinks
`link_wikidata_sitelinks.py --ids <ids...>` sets the `bgwiki` sitelink on each
QID (skips any item that already has one — safe to re-run), writes the
`wd_linked` column in `tracking.csv`, and is resumable. Needs the Wikidata bot
credential at `~/Projects/wiki/wikidata-pybot/` (auto-set as `PYWIKIBOT_DIR`).

### Step 7 — verify and record
Purge each new page so the Taxobox re-reads Wikidata, confirm the two-way link
and that the Taxobox renders family/genus, then:
- set `content_status=published_bot`, `wp_exists=yes`, `wp_url` on each row in
  `tracking.csv`;
- add the new articles under `== Създадени статии ==` on the bot log
  (`wiki/bot/bot-pages/`) and push it (same git workflow).

```bash
# purge (refresh Taxobox) — repeat per title
curl -s -X POST 'https://bg.wikipedia.org/w/api.php' \
  --data-urlencode action=purge --data-urlencode format=json \
  --data-urlencode 'titles=<Bg Title>'
```

## Recovery & details

See [reference.md](reference.md) for git-remote-mediawiki recovery (ref locks,
"Cannot rebase onto multiple branches"), credential/keychain fixes, the
windows-1251 Red Book gotchas, and shell pitfalls (BSD vs GNU, `&&` on grep
exit 1, sticky shell cwd).
