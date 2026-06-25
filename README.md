# Red Book → Bulgarian Wikipedia

A project to create and update Bulgarian Wikipedia articles for the species
listed in the **Red Data Book of the Republic of Bulgaria** (Червена книга на
Република България).

The Red Book has two volumes:

- **Vol. 1 — Plants & Fungi**: http://e-ecodb.bas.bg/rdb/bg/vol1/texts.html
- **Vol. 2 — Animals**: http://e-ecodb.bas.bg/rdb/bg/vol2/texts.html

The master species list comes from the Wikipedia page
[Списък на видовете в Червената книга на Република България](https://bg.wikipedia.org/wiki/Списък_на_видовете_в_Червената_книга_на_Република_България).

Edits are published under the bot account
[Потребител:BOTulechki](https://bg.wikipedia.org/wiki/Потребител:BOTulechki) as
part of an AI agentic workflow: the tracking, reconciliation, and article
drafting/publishing steps are driven by an AI coding agent running these scripts
and the `git-remote-mediawiki` tooling.

Wikidata: conservation status for Red Book taxa is modelled with
[regional conservation status (P14254)](https://www.wikidata.org/wiki/Property:P14254);
see [Wikidata:WikiProject Bulgaria/Red Book](https://www.wikidata.org/wiki/Wikidata:WikiProject_Bulgaria/Red_Book)
for the statement model, SPARQL query, and [QuickStatements batch #259821](https://quickstatements.toolforge.org/#/batch/259821).
Local docs: [`wikidata-modelling/`](wikidata-modelling/).

## Goal

For every species in the Red Book, track its status across the article-creation
workflow and (eventually) create or update the corresponding bg.wikipedia
article. Each step is a column in `tracking.csv`.

## Repository layout

```
red-book/
├── README.md                ← this file
├── tracking.csv             ← master tracking sheet (one row per species)
├── outbox/                  ← Phase B article drafts (.mw), tracked in git
├── drafts/                  ← Phase A briefs (gitignored working copies)
├── wikidata-modelling/      ← P14254 modelling docs + QuickStatements batch
├── scripts/                 ← the data pipeline (see below)
│   ├── common.py            ← shared CSV helpers + column schema + taxon fixes
│   ├── build_tracker.py     ← build tracking.csv from the species-list .mw
│   ├── check_wp_exists.py   ← step 1: does the bg.wikipedia article exist?
│   ├── reconcile_taxa.py    ← step 2: match Latin taxa → Wikidata QIDs
│   ├── build_redbook_map.py ← step 3: match taxa → Red Book (e-ecodb) URLs
│   └── fetch_wp_articles.py ← pull existing bg.wikipedia articles locally
├── data/                    ← scraped/intermediate data (not the source of truth)
│   ├── redbook_index.json   ← {Latin name → Red Book URL} map
│   ├── vol1_texts.html      ← cached Red Book index (plants & fungi)
│   ├── vol2_texts.html      ← cached Red Book index (animals)
│   ├── wp_titles.txt        ← list of article titles to fetch
│   └── wp_fetch_failed.txt  ← titles the fetch script could not clone
└── wiki/                    ← local MediaWiki clones (gitignored)
    ├── species-list/        ← the source list page (single-page git clone)
    ├── articles/            ← reference mirror of existing articles (plain .mw)
    └── bot/bot-pages/       ← bot user page + project log (small git clone)
```

`outbox/` holds new article wikitext (Phase B). Publish with
`scripts/publish_api.py` — seconds per page via the MediaWiki API.

`wiki/articles/` is a **reference mirror** from `fetch_wp_articles.py` (not the
publish path). The bot log at `wiki/bot/bot-pages/` uses a small
`git-remote-mediawiki` clone for occasional log updates.

## The tracking sheet (`tracking.csv`)

One row per species. Columns (defined in `scripts/common.py`):

| Column | Meaning | Filled by |
|---|---|---|
| `id` | sequential id | `build_tracker.py` |
| `group` | `plants_fungi` / `animals` | `build_tracker.py` |
| `redbook_vol` | `vol1` / `vol2` | `build_tracker.py` |
| `bg_name` | Bulgarian name = Wikipedia title | `build_tracker.py` |
| `taxon` | Latin scientific name | `build_tracker.py` |
| `redbook_status` | `CR`/`EN`/`VU`/`RE`/`EX` | `build_tracker.py` |
| `wp_exists` | `yes` / `redirect` / `no` | `check_wp_exists.py` |
| `wp_url` | canonical article URL (when it exists) | `check_wp_exists.py` |
| `wikidata_qid` | Wikidata QID for the taxon | `reconcile_taxa.py` |
| `redbook_url` | e-ecodb.bas.bg article URL | `build_redbook_map.py` |
| `rb_bg_name` | Bulgarian name exactly as on e-ecodb index | `build_redbook_map.py` |
| `rb_taxon` | Latin name exactly as on e-ecodb index | `build_redbook_map.py` |
| `content_status` | `todo`/`draft`/`created`/`published`/`published_bot` | manual |
| `wd_linked` | `yes` once the Wikidata `bgwiki` sitelink is set | `link_wikidata_sitelinks.py` |
| `notes` | warnings, redirects, low-confidence matches | all scripts |

### Current state (snapshot)

- **1095 species** tracked — 808 plants & fungi, 287 animals.
- Red Book status: CR=361, EN=511, VU=180, RE=12, EX=31.
- Wikipedia existence: **395 exist**, 43 redirects, **657 missing**.
- Wikidata QIDs resolved: 1072 / 1095.
- Red Book URLs resolved: 1095 / 1095.
- `content_status`: all `todo` (article creation not started yet).

## The pipeline (how to rebuild the sheet)

All scripts are **resumable** (only process rows with empty target columns) and
**checkpoint** after each batch, with backoff on HTTP 429. Run from the repo root.

```bash
# 1. Build tracking.csv from the species list
python3 scripts/build_tracker.py

# 2. Check which articles already exist on bg.wikipedia (MediaWiki API, batched)
python3 scripts/check_wp_exists.py

# 3. Reconcile Latin taxa to Wikidata QIDs (wikidata.reconci.link, type Q16521)
python3 scripts/reconcile_taxa.py

# 4. Build the taxon → Red Book URL map and fill redbook_url
python3 scripts/build_redbook_map.py
```

Notes:
- `common.py::TAXON_FIXES` corrects a few typos in the source list that would
  otherwise break taxon matching.
- `build_redbook_map.py` folds Cyrillic look-alike letters in Latin names and
  decodes the windows-1251 Red Book pages.

## Publishing new articles

```bash
.venv/bin/python scripts/check_links.py outbox/<Title>.mw
.venv/bin/python scripts/publish_api.py <Title>    # or: scripts/publish.sh <Title>
.venv/bin/python scripts/link_wikidata_sitelinks.py --ids <id>
```

Auth: same `BOTulechki@gitBot` bot password as wikipedia-git (git credential
helper). `publish_api.py` purges after create so the Taxobox can refresh once
the Wikidata sitelink is set.

## Syncable local clones (API mirror)

`wiki/articles/<Title>.mw` is a local mirror of the live wikitext, kept current
via the API by `scripts/sync_articles.py` (no git). `wiki/articles/.revids.json`
records the base revision each copy was synced from — that revid is what makes
edits conflict-safe.

```bash
.venv/bin/python scripts/sync_articles.py                 # all wp_exists=yes rows
.venv/bin/python scripts/sync_articles.py --titles "Алепска млечка"
.venv/bin/python scripts/sync_articles.py --check         # report local-vs-live drift
```

Edit a synced file then push with `publish_api.py --allow-existing` — the synced
`baserevid` is sent so a concurrent/human edit triggers an edit conflict instead
of being overwritten.

After publishing new articles, update the bot project log on Wikipedia
(`wiki/bot/bot-pages/`):

```bash
cd wiki/bot/bot-pages
# edit Потребител:BOTulechki%2FВидове_от_Червената_Книга.mw — append to == Създадени статии == (creation order, not alphabetical)
git commit -am "Добавена статия …"
git push && git pull --rebase
```

The project page lives at
[Потребител:BOTulechki/Видове от Червената Книга](https://bg.wikipedia.org/wiki/Потребител:BOTulechki/Видове_от_Червената_Книга)
(linked from [Потребител:BOTulechki](https://bg.wikipedia.org/wiki/Потребител:BOTulechki)).

Add a reference article to the local mirror:

```bash
python3 scripts/fetch_wp_articles.py --limit 10   # or full run
```

Re-fetching everything is in `scripts/fetch_wp_articles.py`; failed titles are
recorded in `data/wp_fetch_failed.txt`.

## Known issues / next steps

- **API publish — DONE.** New articles go `outbox/` → `publish_api.py` (fast).
  The old mega `wiki/articles/` git-remote clone is reference-only.
- **Article creation not started** — `content_status` is `todo` for every row.
- ~23 taxa still lack a Wikidata QID (low-confidence or no candidate; see `notes`).

## Workflow history (for reference)

This project was built incrementally across several agent sessions:

1. **Project setup & pipeline** — understood the Red Book sources, mirrored the
   `wikipedia-git` workflow, pulled the species-list page, and built
   `tracking.csv` plus steps 1–3 of the pipeline
   (`build_tracker`, `check_wp_exists`, `reconcile_taxa`, `build_redbook_map`).
2. **URL normalization** — decoded percent-encoded Cyrillic Wikipedia URLs in
   `tracking.csv` to plaintext, then began checking out the pages locally.
3. **Bulk article fetch** — ran/iterated on `fetch_wp_articles.py` to download
   existing articles into `wiki/articles/`.
4. **Flatten layout** — moved nested `wiki/articles/<Title>/<Title>.mw` files up
   to flat `wiki/articles/<Title>.mw` and updated the fetch script accordingly.

## Requirements

- Python 3 with `requests` (for the API/reconciliation/scraping scripts).
- `git-remote-mediawiki` tooling installed at `~/Projects/admin/wikipedia-git/`
  (Homebrew git + Perl `Git-Mediawiki`), used by `fetch_wp_articles.py`.
