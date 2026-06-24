"""Shared bg.wikipedia MediaWiki API client for the red-book project."""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass

import requests

BG_HOST = os.environ.get("MW_HOST", "bg.wikipedia.org")
BG_PATH = os.environ.get("MW_PATH", "w")
BG_API = f"https://{BG_HOST}/{BG_PATH}/api.php"
DEFAULT_LOGIN = os.environ.get("MW_LOGIN", "BOTulechki@gitBot")
UA = "red-book-tracker/0.1 (Wikipedia article-creation project)"


@dataclass
class BotCredentials:
    username: str
    password: str


@dataclass
class PageContent:
    title: str
    exists: bool
    text: str = ""
    revid: int = 0
    timestamp: str = ""


class EditConflict(RuntimeError):
    """Raised when the wiki rejects an edit because the base revision moved."""


def git_credential_fill(host: str, path: str, username: str) -> BotCredentials:
    """Read bot password from git's credential helper (same store as wikipedia-git)."""
    payload = f"protocol=https\nhost={host}\npath={path}\nusername={username}\n\n"
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git credential fill failed for {username}@{host}/{path}. "
            "Run setup-auth.sh in a wiki clone or store the token with "
            "`git credential approve`."
        )
    fields: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k] = v
    user = fields.get("username", username)
    password = fields.get("password", "")
    if not password:
        raise RuntimeError(
            f"No password returned for {username}@{host}. "
            "Re-run ~/Projects/admin/wikipedia-git/setup-auth.sh in a wiki clone."
        )
    return BotCredentials(username=user, password=password)


class MediaWikiClient:
    def __init__(
        self,
        *,
        host: str = BG_HOST,
        path: str = BG_PATH,
        login: str = DEFAULT_LOGIN,
        credentials: BotCredentials | None = None,
    ) -> None:
        self.host = host
        self.path = path
        self.api = f"https://{host}/{path}/api.php"
        self.login_name = login
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})
        self._logged_in = False
        self._credentials = credentials

    def _get(self, **params: str) -> dict:
        return self._request("GET", params)

    def _post(self, **params: str) -> dict:
        return self._request("POST", params)

    def _request(
        self, method: str, params: dict[str, str], *, raise_on_error: bool = True
    ) -> dict:
        wait = 5.0
        for attempt in range(6):
            if method == "GET":
                resp = self.session.get(self.api, params=params, timeout=120)
            else:
                resp = self.session.post(self.api, data=params, timeout=120)
            if resp.status_code == 429:
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                code = data["error"].get("code", "")
                if code in ("maxlag", "ratelimited") and attempt + 1 < 6:
                    time.sleep(wait)
                    wait = min(wait * 2, 60)
                    continue
                if not raise_on_error:
                    return data
                raise RuntimeError(
                    f"API error {code}: {data['error'].get('info', data['error'])}"
                )
            return data
        raise RuntimeError("API request failed after retries")

    def login(self) -> None:
        if self._logged_in:
            return
        creds = self._credentials or git_credential_fill(self.host, self.path, self.login_name)
        token_data = self._get(action="query", meta="tokens", type="login", format="json")
        login_token = token_data["query"]["tokens"]["logintoken"]
        login_data = self._post(
            action="login",
            lgname=creds.username,
            lgpassword=creds.password,
            lgtoken=login_token,
            format="json",
        )
        if login_data.get("login", {}).get("result") != "Success":
            result = login_data.get("login", {})
            raise RuntimeError(
                f"Login failed: {result.get('result')} — {result.get('reason', result)}"
            )
        self._logged_in = True

    def csrf_token(self) -> str:
        self.login()
        data = self._get(action="query", meta="tokens", type="csrf", format="json")
        return data["query"]["tokens"]["csrftoken"]

    def page_exists(self, title: str) -> bool:
        data = self._get(
            action="query",
            format="json",
            prop="info",
            titles=title,
        )
        page = next(iter(data["query"]["pages"].values()))
        return "missing" not in page

    def get_pages(self, titles: list[str]) -> dict[str, PageContent]:
        """Fetch current wikitext + revid + timestamp for titles (batched, redirects followed)."""
        out: dict[str, PageContent] = {}
        uniq = sorted({t for t in titles if t})
        for i in range(0, len(uniq), 50):
            chunk = uniq[i : i + 50]
            data = self._get(
                action="query",
                format="json",
                prop="revisions",
                rvprop="ids|timestamp|content",
                rvslots="main",
                redirects="1",
                titles="|".join(chunk),
            ).get("query", {})
            norm = {n["from"]: n["to"] for n in data.get("normalized", [])}
            redir = {r["from"]: r["to"] for r in data.get("redirects", [])}
            by_title: dict[str, PageContent] = {}
            for p in data.get("pages", {}).values():
                title = p.get("title", "")
                if "missing" in p:
                    by_title[title] = PageContent(title=title, exists=False)
                    continue
                rev = (p.get("revisions") or [{}])[0]
                slot = rev.get("slots", {}).get("main", {})
                by_title[title] = PageContent(
                    title=title,
                    exists=True,
                    text=slot.get("*", slot.get("content", "")),
                    revid=int(rev.get("revid", 0)),
                    timestamp=rev.get("timestamp", ""),
                )
            for title in chunk:
                t = redir.get(norm.get(title, title), norm.get(title, title))
                out[title] = by_title.get(
                    t, PageContent(title=title, exists=False)
                )
            time.sleep(0.3)
        return out

    def get_page(self, title: str) -> PageContent:
        return self.get_pages([title])[title]

    def edit_page(
        self,
        title: str,
        text: str,
        summary: str,
        *,
        createonly: bool = True,
        baserevid: int | None = None,
        basetimestamp: str | None = None,
    ) -> dict:
        """Create or edit a page.

        Pass baserevid (and optionally basetimestamp) to make the edit
        conflict-safe: the wiki rejects it (-> EditConflict) if the page moved on
        since that revision, instead of clobbering concurrent edits.
        """
        self.login()
        params: dict[str, str] = {
            "action": "edit",
            "format": "json",
            "title": title,
            "text": text,
            "summary": summary,
            "token": self.csrf_token(),
        }
        if createonly:
            params["createonly"] = "1"
        if baserevid is not None:
            params["baserevid"] = str(baserevid)
        if basetimestamp:
            params["basetimestamp"] = basetimestamp
        data = self._request("POST", params, raise_on_error=False)
        if "error" in data:
            code = data["error"].get("code", "")
            info = data["error"].get("info", data["error"])
            if code == "editconflict":
                raise EditConflict(f"edit conflict on {title!r}: {info}")
            raise RuntimeError(f"API error {code}: {info}")
        return data.get("edit", data)

    def purge(self, title: str) -> None:
        self.login()
        self._post(
            action="purge",
            format="json",
            titles=title,
            token=self.csrf_token(),
        )
