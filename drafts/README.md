# Writer briefs (Phase A output)

Intermediate artifacts for the three-phase publish workflow. Each species gets a
folder:

```
drafts/<id>_<Bg_Title>/
  brief.md          structured facts for Opus
  redbook.txt       full Red Book entry
  skeleton.wikitext Taxobox + section placeholders
```

Generate with:

```bash
.venv/bin/python scripts/select_candidates.py --n 5   # verify candidates
.venv/bin/python scripts/prepare_brief.py 11 12       # or specific ids
```

Draft folders are gitignored (local working copies). Do not commit unless you
want to share a brief for review.
