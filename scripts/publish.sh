#!/usr/bin/env bash
# Publish one or more articles to bg.wikipedia via the MediaWiki API (fast path).
#
# Reads wikitext from outbox/<Title>.mw (legacy fallback: wiki/articles/).
# Auth: same bot password as wikipedia-git (git credential helper).
#
# Usage:
#   scripts/publish.sh Винчелистен_лопен
#   PUBLISH_SUMMARY="нова статия" scripts/publish.sh Title1 Title2
#
# Pass titles as the .mw basenames WITHOUT the extension (underscores ok).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${REPO}/.venv/bin/python"
PUBLISH="${REPO}/scripts/publish_api.py"

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <Title_Without_Ext> [more...]" >&2
  exit 2
fi

if [ ! -x "$PYTHON" ]; then
  echo "!! missing venv: $PYTHON — run: python3 -m venv .venv && .venv/bin/pip install requests" >&2
  exit 1
fi

exec "$PYTHON" "$PUBLISH" "$@"
