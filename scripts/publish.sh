#!/usr/bin/env bash
# Publish one or more new/edited articles to bg.wikipedia via git-remote-mediawiki.
#
# Handles the recurring failure modes so you don't re-derive them:
#   - registers each title in remote.origin.pages (idempotent)
#   - commits with a Bulgarian edit summary (override with PUBLISH_SUMMARY=...)
#   - push always rejects non-fast-forward first -> pull --rebase, with a
#     fallback to `git rebase origin/master` ("Cannot rebase onto multiple
#     branches") and a ref-lock recovery, then push.
#
# pull/push re-list ALL tracked pages and take 1-3 min. That is NOT a hang.
#
# Usage:
#   scripts/publish.sh Алпийски_корал Андрахне
#   PUBLISH_SUMMARY="нова статия от Червената книга" scripts/publish.sh Андрахне
#
# Pass titles as the .mw basenames WITHOUT the extension (underscores ok).
set -uo pipefail

ACTIVATE="$HOME/Projects/admin/wikipedia-git/activate.sh"
REPO="$HOME/Projects/wiki/red-book"
ARTICLES="$REPO/wiki/articles"
SUMMARY="${PUBLISH_SUMMARY:-нова статия от Червената книга на България}"

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <Title_Without_Ext> [more...]" >&2
  exit 2
fi

# shellcheck disable=SC1090
. "$ACTIVATE"
cd "$ARTICLES" || { echo "no $ARTICLES" >&2; exit 1; }

# 1. register pages + stage files
existing_pages="$(git config --get-all remote.origin.pages 2>/dev/null || true)"
to_add=()
for title in "$@"; do
  file="${title}.mw"
  if [ ! -f "$file" ]; then
    echo "!! missing file: $ARTICLES/$file" >&2
    exit 1
  fi
  if ! grep -qxF "$title" <<<"$existing_pages"; then
    git config --add remote.origin.pages "$title"
    echo "registered page: $title"
  fi
  to_add+=("$file")
done
git add -- "${to_add[@]}"

# 2. commit (skip cleanly if nothing staged)
if git diff --cached --quiet; then
  echo "nothing staged to commit; will still sync + push."
else
  git commit -m "$SUMMARY" || { echo "commit failed" >&2; exit 1; }
fi

# 3. sync: pull --rebase, fall back to explicit rebase, then ref-lock recovery
echo "=== syncing with live wiki (re-lists all pages; 1-3 min) ==="
if ! git pull --rebase 2>&1; then
  echo "pull --rebase failed; trying explicit rebase onto origin/master"
  if ! git rebase origin/master 2>&1; then
    echo "rebase failed; attempting ref-lock recovery"
    git rebase --abort 2>/dev/null || true
    if git show-ref --verify --quiet refs/mediawiki/origin/master; then
      git update-ref refs/remotes/origin/master refs/mediawiki/origin/master
      git rebase origin/master 2>&1 || { echo "still failing; resolve by hand" >&2; exit 1; }
    else
      echo "no refs/mediawiki/origin/master to recover from; resolve by hand" >&2
      exit 1
    fi
  fi
fi

# 4. push
echo "=== pushing to bg.wikipedia ==="
if ! git push 2>&1; then
  echo "push failed; re-syncing once and retrying"
  git pull --rebase 2>&1 || git rebase origin/master 2>&1
  git push 2>&1 || { echo "push still failing; resolve by hand" >&2; exit 1; }
fi

echo "=== done. published: $* ==="
echo "next: scripts/link_wikidata_sitelinks.py --ids <ids> ; then purge + update tracking.csv + bot log"
