"""Local mirror of bg.wikipedia article wikitext + per-page revision index.

This is the "syncable local clone" layer for the API workflow. Each tracked page
is stored as wiki/articles/<Title>.mw, and wiki/articles/.revids.json records the
base revision each local copy was synced from. That revid is what makes API edits
conflict-safe: we send it as `baserevid` so the wiki rejects our edit if the page
moved on under us (instead of blindly overwriting).

Filename convention matches git-remote-mediawiki / wikipedia-git:
spaces -> underscores, "/" -> "%2F".
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MIRROR = REPO / "wiki" / "articles"
INDEX = MIRROR / ".revids.json"


def title_to_filename(title: str) -> str:
    return title.replace(" ", "_").replace("/", "%2F") + ".mw"


def filename_to_title(name: str) -> str:
    stem = name[:-3] if name.endswith(".mw") else name
    return stem.replace("%2F", "/").replace("_", " ")


def article_path(title: str) -> Path:
    return MIRROR / title_to_filename(title)


def load_index() -> dict[str, dict]:
    if not INDEX.exists():
        return {}
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_index(index: dict[str, dict]) -> None:
    MIRROR.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def get_base(title: str) -> dict | None:
    """Return {revid, timestamp, synced_at} for the locally synced copy, if any."""
    return load_index().get(title)


def record_revision(
    title: str,
    revid: int | str,
    timestamp: str | None = None,
    *,
    synced_at: str | None = None,
) -> None:
    index = load_index()
    entry = index.get(title, {})
    entry["revid"] = int(revid)
    if timestamp:
        entry["timestamp"] = timestamp
    if synced_at:
        entry["synced_at"] = synced_at
    index[title] = entry
    save_index(index)


def write_article(title: str, text: str) -> Path:
    MIRROR.mkdir(parents=True, exist_ok=True)
    p = article_path(title)
    p.write_text(text, encoding="utf-8")
    return p


def read_article(title: str) -> str | None:
    p = article_path(title)
    return p.read_text(encoding="utf-8") if p.is_file() else None
