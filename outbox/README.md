# Article outbox (Phase B output)

Finished wikitext drafts live here before publish. This folder is **tracked in
git** (unlike `wiki/`, which holds reference mirrors and bot-page clones).

## Workflow

1. **Phase B (Opus)** writes `outbox/<Bg_Title_With_Underscores>.mw`
2. **Phase C** runs `check_links.py` then `publish_api.py`

```bash
.venv/bin/python scripts/check_links.py outbox/Винчелистен_лопен.mw
.venv/bin/python scripts/publish_api.py Винчелистен_лопен
```

Publishing uses the MediaWiki API (~seconds per page), not the old 360-page
`git-remote-mediawiki` sync.
