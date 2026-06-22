#!/usr/bin/env python3
"""Clone bg.wikipedia species articles locally via git-remote-mediawiki.

Each article is fetched via a shallow clone (cached under wiki/.article-clones/)
and saved as wiki/articles/<Title>.mw. Re-run to fetch any missing pages.

    python3 scripts/fetch_wp_articles.py
    python3 scripts/fetch_wp_articles.py --limit 10   # smoke test
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parent.parent
ADMIN = Path.home() / "Projects/admin/wikipedia-git"
API = "https://bg.wikipedia.org/w"
OUT = REPO / "wiki" / "articles"
CLONES = REPO / "wiki" / ".article-clones"
TRACKING = REPO / "tracking.csv"
SLEEP_SEC = 10
MAX_RETRIES = 6
RETRY_BASE_SEC = 30


def git_env() -> dict[str, str]:
    tools = ADMIN / ".tools"
    git_exec = Path("/opt/homebrew/bin/git")
    perl5 = tools / "perl5/lib/perl5"
    git_perl = git_exec.parent.parent / "share/perl5"
    env = os.environ.copy()
    env["PATH"] = f"{tools / 'Git-Mediawiki'}:/opt/homebrew/bin:{env.get('PATH', '')}"
    env["PERL5LIB"] = ":".join(
        str(p)
        for p in (perl5, tools / "Git-Mediawiki", git_perl)
        if p.exists()
    )
    return env


def load_titles() -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    with TRACKING.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            url = row.get("wp_url", "").strip()
            if not url.startswith("https://bg.wikipedia.org/wiki/"):
                continue
            title = unquote(url.split("/wiki/", 1)[1]).replace(" ", "_")
            if title and title not in seen:
                seen.add(title)
                titles.append(title)
    return titles


def clone_done(title: str) -> bool:
    return (OUT / f"{title}.mw").is_file()


def clone_page(title: str, env: dict[str, str]) -> bool:
    target = CLONES / title
    dest = OUT / f"{title}.mw"
    if clone_done(title):
        return True

    if not target.exists():
        clone_cmd = [
            "git",
            "clone",
            "--no-checkout",
            "-c",
            f"remote.origin.pages={title}",
            "-c",
            "remote.origin.mediaImport=false",
            "-c",
            "remote.origin.shallow=true",
            f"mediawiki::{API}",
            str(target),
        ]

        for attempt in range(MAX_RETRIES):
            try:
                subprocess.run(clone_cmd, check=True, env=env, cwd=REPO, capture_output=True, text=True)
                break
            except subprocess.CalledProcessError as exc:
                err = (exc.stderr or "") + (exc.stdout or "")
                if "429" in err and attempt + 1 < MAX_RETRIES:
                    wait = RETRY_BASE_SEC * (2**attempt)
                    print(f"  rate limited; retry in {wait}s ({attempt + 1}/{MAX_RETRIES})")
                    time.sleep(wait)
                    if target.exists():
                        import shutil

                        shutil.rmtree(target)
                    continue
                raise
        else:
            return False

    try:
        subprocess.run(
            ["git", "checkout", "master"],
            check=True,
            env=env,
            cwd=target,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        import shutil

        shutil.rmtree(target)
        return False

    src = target / f"{title}.mw"
    if not src.is_file():
        return False

    OUT.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return clone_done(title)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="fetch at most N pages (for testing)")
    parser.add_argument("--sleep", type=float, default=SLEEP_SEC, help="seconds between fetches")
    args = parser.parse_args()

    if not (ADMIN / "activate.sh").is_file():
        sys.exit(f"wikipedia-git not installed at {ADMIN}")

    titles = load_titles()
    if args.limit:
        titles = titles[: args.limit]

    OUT.mkdir(parents=True, exist_ok=True)
    env = git_env()

    done = skipped = failed = 0
    failed_titles: list[str] = []
    print(f"Fetching {len(titles)} articles (one shallow clone each)")

    for i, title in enumerate(titles, 1):
        if clone_done(title):
            skipped += 1
            continue
        print(f"[{i}/{len(titles)}] {title}")
        try:
            if clone_page(title, env):
                done += 1
            else:
                print("  ✗ no .mw file after clone")
                failed += 1
                failed_titles.append(title)
        except subprocess.CalledProcessError:
            print("  ✗ clone failed")
            failed += 1
            failed_titles.append(title)
        if i < len(titles):
            time.sleep(args.sleep)

    if failed_titles:
        fail_path = REPO / "data" / "wp_fetch_failed.txt"
        fail_path.write_text("\n".join(failed_titles) + "\n", encoding="utf-8")
        print(f"Failed titles written to {fail_path.relative_to(REPO)}")

    total = len(list(OUT.glob("*.mw")))
    print(f"\nDone. fetched={done}, skipped={skipped}, failed={failed}, on disk={total}")


if __name__ == "__main__":
    main()
