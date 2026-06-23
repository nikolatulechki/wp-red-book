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

## Goal

For every species in the Red Book, track its status across the article-creation
workflow and (eventually) create or update the corresponding bg.wikipedia
article. Each step is a column in `tracking.csv`.

## Repository layout

```
red-book/
├── README.md                ← this file
├── tracking.csv             ← master tracking sheet (one row per species)
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
└── wiki/                    ← local MediaWiki clones (git-remote-mediawiki)
    ├── species-list/        ← the source list page (single-page git clone)
    ├── articles/            ← ALL article pages in ONE git clone, as <Title>.mw
    └── bot/bot-pages/       ← bot user page + project log subpage
```

`wiki/articles/` is a single `git-remote-mediawiki` clone that tracks every
article as a page in `remote.origin.pages`. Edits to any `.mw` file are
committed and pushed back to bg.wikipedia together (see the global
`wikipedia-git` skill for the workflow).

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

## Fetching article wikitext locally

Existing bg.wikipedia articles live in a **single** `git-remote-mediawiki` clone
at `wiki/articles/` (see the global `wikipedia-git` skill). The tooling lives at
`~/Projects/admin/wikipedia-git/`. All ~350 pages are tracked in one repo's
`remote.origin.pages`, so they can be committed and pushed back together.

**Authentication is required** — bulk fetch/push of hundreds of pages gets
rate-limited (HTTP 429) when anonymous. The clone is configured with
`remote.origin.mwLogin` (bot password stored in the macOS keychain).

Daily workflow:

```bash
. ~/Projects/admin/wikipedia-git/activate.sh
cd wiki/articles
# edit <Title>.mw files
git commit -am "Edit summary shown on the wiki"   # in Bulgarian
git push
git pull --rebase
```

After publishing new articles, update the bot project log on Wikipedia
(`wiki/bot/bot-pages/`):

```bash
cd wiki/bot/bot-pages
# edit Потребител:BOTulechki%2FВидове_от_Червената_Книга.mw — add the new article to == Създадени статии ==
git commit -am "Добавена статия …"
git push && git pull --rebase
```

The project page lives at
[Потребител:BOTulechki/Видове от Червената Книга](https://bg.wikipedia.org/wiki/Потребител:BOTulechki/Видове_от_Червената_Книга)
(linked from [Потребител:BOTulechki](https://bg.wikipedia.org/wiki/Потребител:BOTulechki)).

Add a new article to track:

```bash
cd wiki/articles
git config --add remote.origin.pages '<New_Title_With_Underscores>'
git fetch origin && git checkout master
```

Re-fetching everything (rebuild the clone) is in
`scripts/fetch_wp_articles.py`; failed titles are recorded in
`data/wp_fetch_failed.txt`.

## Known issues / next steps

- **Single-repo layout — DONE.** `wiki/articles/` is now one
  `git-remote-mediawiki` clone tracking all pages (replacing the old
  per-article throwaway clones). Fixing the bulk workflow required two patches
  to the shared tooling at `~/Projects/admin/wikipedia-git/`:
  (1) an off-by-one in the helper's page-list batching that sent 51 titles per
  query instead of 50 (the MediaWiki API caps `titles` at 50), and
  (2) enabling `MediaWiki::API` retries + `maxlag` in `connect_maybe`, since the
  module defaulted to zero retries and died on the first rate-limit (429).
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
