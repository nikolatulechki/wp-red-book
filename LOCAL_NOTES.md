# Local notes

Wikipedia
- TODO after all articles are created 
    - check that all taxoboxes contain the bulgarian red book line
    - create redirects from latin names in bg namespace — see `.cursor/skills/red-book-publish/reference.md` § “bg.wikipedia redirects”
   
Wikidata work    
    - add wikidata prop so that we can track designation there 
    - fix: regional conservation status: extinct species to 'regionally extinct'
    - hunt down the one missing

Community 
    - follow-up about adding missing illustrations

Bot

## bg.wikipedia redirects (Latin → Bulgarian)

Planned batch task (see `LOCAL_NOTES.md`): after Red Book articles exist, create
**main-namespace redirect pages** from each Latin scientific name (`taxon`) to
the canonical Bulgarian article title.

### What a redirect is

A redirect is a normal wiki page whose entire content is one magic-word line.
When a reader opens that title, follows a `[[link]]` to it, or searches for it,
MediaWiki sends them to the target article.

On **bg.wikipedia** prefer the local magic word:

```wikitext
#ПРЕНАСОЧВАНЕ [[Ленолистно секирче]]
```

`#REDIRECT` also works on most wikis, but `#ПРЕНАСОЧВАНЕ` is the bg convention.

Rules:

- The redirect line must be **first** (only whitespace before it).
- Target is a normal wikilink with spaces: `[[Page title]]`, not underscores.
- No taxobox, categories, or article prose on redirect pages.
- The API marks redirect pages with a `redirect` flag; with `redirects=1`,
  queries follow them to the final page.

### Latin name → Bulgarian article (this project)

For each published species:

| Field | Role |
| --- | --- |
| Redirect **from** | `taxon` column (e.g. `Lathyrus linifolius`) |
| Redirect **to** | canonical Bulgarian title (see below) |
| Local file name | `outbox/Lathyrus_linifolius.mw` (underscores) |

Example wikitext:

```wikitext
#ПРЕНАСОЧВАНЕ [[Ленолистно секирче]]
```

**Wikidata:** keep the `bgwiki` sitelink on the **Bulgarian** title only. The
Latin page is a convenience redirect for search and `[[Latin name]]` links — it
does not get its own sitelink.

**Inside articles:** the Latin name already appears in italics in the lead
(`(''Lathyrus linifolius'')`). That is prose, not a redirect. Redirects are
separate pages.

### How `tracking.csv` already uses “redirect”

`check_wp_exists.py` sets `wp_exists` to `yes | redirect | no` by querying the
**Bulgarian name** (`bg_name`), not the Latin name:

| `wp_exists` | Meaning |
| --- | --- |
| `yes` | `bg_name` is a real article |
| `redirect` | `bg_name` exists but redirects elsewhere (Bulgarian synonym → canonical title) |
| `no` | page missing |

The ~43 existing `redirect` rows are *not* Latin→Bulgarian. Example: “Снежно
кокиче” → “Обикновено кокиче”. The canonical target is in `wp_url` and in
`notes` as `WP redirect -> …`.

When creating a Latin redirect, the **target** must be the **final** Bulgarian
article, not an intermediate redirect title:

- If `wp_exists=yes` → target is `bg_name`.
- If `wp_exists=redirect` → target is the title from `wp_url` / notes (strip the
  `https://bg.wikipedia.org/wiki/` prefix and replace `_` with spaces).

Avoid double redirects (`Latin → bg_name → canonical`).

### Publishing redirects (when ready)

No dedicated redirect script yet. Same path as new articles:

```bash
# one-line .mw in outbox/
.venv/bin/python scripts/publish_api.py Lathyrus_linifolius
```

`publish_api.py` uses `createonly` — it skips titles that already exist instead
of overwriting. Suggested edit summary:
`пренасочване към българската статия (Червена книга)`.

`check_links.py` and `select_candidates.py` already treat followed redirects as
“page exists” (`redirects=1`).

### Edge cases

1. **Taxon variants** — use the exact string from `taxon` / `rb_taxon`
   (including `subsp.`, `var.`).
2. **Taxon mismatches** — if `wd_taxon` ≠ `taxon`, pick one canonical Latin
   string (usually `taxon` from the Red Book list).
3. **Pre-check** — query the API for the Latin title before creating; skip or
   handle if it already exists as an article, redirect, or disambiguation page.
4. **No categories on redirects** — unlike full articles (categories are a
   separate batch pass anyway).

### What redirects do *not* do

- Do not replace Wikidata sitelinks or Taxobox data.
- Do not fix red links to wrong **Bulgarian** titles — only links to the
  **Latin page title** benefit.
- Are not the same as `{{Препратка}}` (“soft redirects”) used for near-miss
  titles.
