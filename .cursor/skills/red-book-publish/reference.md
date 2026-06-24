# Reference — recovery & gotchas

Detailed notes for the `red-book-publish` workflow. Read the section you need;
don't load all of it by default.

## git-remote-mediawiki publish recovery (legacy — bot log only)

**New articles:** use `scripts/publish_api.py` (fast API path). The notes below
apply only if you are pushing via git-remote-mediawiki — e.g. the bot project log
at `wiki/bot/bot-pages/`.

`scripts/publish.sh` now delegates to `publish_api.py`; it no longer syncs the
old mega `wiki/articles/` clone.

### API publish auth

Uses the same `BOTulechki@gitBot` token as wikipedia-git:

```bash
printf 'protocol=https\nhost=bg.wikipedia.org\npath=w\nusername=BOTulechki@gitBot\n' \
  | git credential fill   # should return password=...
```

Re-store with `setup-auth.sh` in any wiki clone if fill returns nothing.

### Bot log clone (git-remote-mediawiki)
The live wiki almost always has revisions your local clone lacks. Push is
rejected. Fix (bot log clone only):

```bash
. ~/Projects/admin/wikipedia-git/activate.sh
cd ~/Projects/wiki/red-book/wiki/bot/bot-pages
git pull --rebase || git rebase origin/master
git push
```

### Non-fast-forward on push (articles mega-clone — deprecated)
If you still use the old `wiki/articles/` git clone:

```bash
. ~/Projects/admin/wikipedia-git/activate.sh
cd ~/Projects/wiki/red-book/wiki/articles
git pull --rebase || git rebase origin/master
git push
```

### "Cannot rebase onto multiple branches"
`git pull --rebase` can choke on ambiguous upstream config because
git-remote-mediawiki creates several remote refs. Rebase the single ref
explicitly instead:

```bash
git rebase origin/master && git push
```

### Ref-lock error (`cannot lock ref refs/remotes/origin/master`)
The fetch imported revisions but couldn't update the tracking ref (it moved
under git). Align the tracking ref to the mediawiki ref, then fast-forward:

```bash
git update-ref refs/remotes/origin/master refs/mediawiki/origin/master
git pull --ff-only   # or: git rebase origin/master
```

### Push/pull looks hung (git-remote only)
A git-remote-mediawiki pull/push re-lists **all** tracked pages in that clone.
The old `wiki/articles/` mega-clone had ~360 pages (1–3 min). Do not use it for
publishing new articles.

### Credential "Device not configured" in background
Means git tried to prompt with no TTY. Re-store the bot credential so the
helper resolves it non-interactively:

```bash
printf 'protocol=https\nhost=bg.wikipedia.org\npath=w\nusername=BOTulechki@gitBot\npassword=<token>\n' \
  | git credential approve
git credential fill <<< $'protocol=https\nhost=bg.wikipedia.org\npath=w\nusername=BOTulechki@gitBot\n'  # verify
```

## Wikidata sitelink

- The article must be **live before** setting the sitelink — Wikidata refuses a
  sitelink to a non-existent page. So publish (step 5) before linking (step 6).
- Setting a sitelink that conflicts with an existing one errors;
  `link_wikidata_sitelinks.py` skips items that already have a `bgwiki` link.
- Auth is a **separate** Wikidata bot password (not the bgwiki git password),
  configured at `~/Projects/wiki/wikidata-pybot/` (`user-config.py` +
  `user-password.py`). The script exports `PYWIKIBOT_DIR` automatically.
- `delay(1)` between writes. A long "Sleeping for N seconds" line is WDQS maxlag
  backoff, not a hang.

### Optional: add a `set_sitelink` helper to wikidata-pybot
The library (`~/Projects/wiki/wikidata-pybot/`) has no `set_sitelink` primitive
yet (only `get_repo`, `get_item`, `delay`). `link_wikidata_sitelinks.py` calls
`item.setSitelink(...)` directly. If you start linking hundreds of rows,
promote it to a reusable primitive in `entities.py` / `__init__.py` (underlying
API action `wbsetsitelink`).

## Red Book (e-ecodb.bas.bg) gotchas

- Pages are **windows-1251**, not UTF-8: `resp.content.decode("windows-1251")`.
  `fetch_sources.py` does this for you.
- Article filenames are **abbreviated and unguessable** (e.g. `Rokessle.html`);
  always use the `redbook_url` already stored in `tracking.csv`.
- The index/entries contain dirty data: unescaped HTML entities (`&#168;` = ¨),
  Cyrillic look-alike letters inside "Latin" names, and duplicated words. The
  taxon→URL map is already built; don't re-scrape unless `redbook_url` is empty.
- Entry layout → wiki sections is in `TEMPLATE.md` §2.

## Shell pitfalls seen in this project

- **macOS = BSD tools.** `grep -P` is unavailable; use `rg` or Python. `wc -w`
  miscounts Cyrillic — count lines, not words.
- **`&&` chains break on `grep` exit 1** (no match is a non-zero exit). Use `;`
  between independent steps, or guard with `|| true`.
- **The shell keeps its cwd between calls.** After a `cd wiki/bot/bot-pages`, a
  later relative `cd` may fail. Use absolute paths or check `pwd` first.
- **Sandbox**: `tee` into the repo can fail with *Operation not permitted*;
  write logs to `/tmp` or run network/publish steps as approved commands.

## tracking.csv columns this workflow touches

- `content_status`: set to `published_bot` for bot-created articles.
- `wp_exists` / `wp_url`: set to `yes` / the live URL after publish.
- `wd_linked`: `yes` once the `bgwiki` sitelink is set (written by
  `link_wikidata_sitelinks.py`).
- `notes`: short audit trail, e.g. `Article + Wikidata bgwiki sitelink created
  by bot <date>`.
