"""Recupere les futurs publics de sp2050.org dans var/sp2050."""

from __future__ import annotations

import json
import re
import threading
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from sp2050.library import cache_dir, catalog_mtime, normalize_body, save_library, story_stamp

ORIGIN = "https://sp2050.org"
INDEX_URL = ORIGIN + "/futurs"
KIOSK_URL = ORIGIN + "/kiosk/futurs.json"
_USER_AGENT = "SP2050-kiosk/1.0"
_FUTUR_PATH = re.compile(r"^/futurs/(\d+)/?$")
_MAX_AGE = 6 * 3600
_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
}

_lock = threading.Lock()
_state = {"running": False}
_thread: threading.Thread | None = None


def running() -> bool:
    with _lock:
        return bool(_state["running"])


def maybe_start(force=False, max_age=_MAX_AGE):
    """Lance une synchro en fond si le cache est absent ou ancien."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        if not force and catalog_mtime() and (time.time() - catalog_mtime()) < max_age:
            return
        _state["running"] = True
        _thread = threading.Thread(target=_background, name="sp2050-sync", daemon=True)
        _thread.start()


def _background():
    try:
        sync()
    finally:
        with _lock:
            _state["running"] = False


def cover_download_url(url: str) -> str:
    """JPEG serre, assez net pour une carte de 340 px."""
    marker = "/image/upload/"
    if "res.cloudinary.com" not in (url or "") or marker not in url:
        return url
    head, tail = url.split(marker, 1)
    path, _, query = tail.partition("?")
    parts = [part for part in path.split("/") if part]
    while parts and _is_transform(parts[0]):
        parts.pop(0)
    built = f"{head}{marker}c_fill,w_480,h_672,q_auto,f_jpg/{'/'.join(parts)}"
    if query:
        built += "?" + query
    return built


def _is_transform(part: str) -> bool:
    if len(part) > 1 and part[0] == "v" and part[1:].isdigit():
        return False
    return "," in part or part.startswith(("c_", "w_", "h_", "q_", "f_", "g_", "e_"))


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = []
        self.hrefs = []
        self.next_href = None
        self.reading_time = ""
        self._want_reading = False
        self._capture_reading = False
        self._body = []
        self._body_depth = 0

    def handle_starttag(self, tag, attrs):
        ad = {key: value or "" for key, value in attrs}
        if tag == "meta":
            key = ad.get("property") or ad.get("name") or ""
            if key:
                self.metas.append((key, ad.get("content") or ""))
        if tag == "a":
            href = ad.get("href") or ""
            if href:
                self.hrefs.append(href)
            rel = set((ad.get("rel") or "").split())
            if href and "next" in rel and self.next_href is None:
                self.next_href = href
        if tag == "link":
            rel = set((ad.get("rel") or "").split())
            href = ad.get("href") or ""
            if href and "next" in rel and self.next_href is None:
                self.next_href = href
        classes = set(ad.get("class", "").split())
        if tag == "span" and "tabular-nums" in classes and self._want_reading:
            self._capture_reading = True
            self._want_reading = False
        if self._body_depth:
            if tag not in _VOID:
                self._body_depth += 1
            if tag == "br":
                self._body.append("\n")
            elif tag == "p" and self._body and not "".join(self._body).endswith("\n"):
                self._body.append("\n\n")
            return
        if tag == "div" and "body-content" in classes:
            self._body_depth = 1

    def handle_endtag(self, tag):
        if self._body_depth and tag not in _VOID:
            self._body_depth -= 1

    def handle_data(self, data):
        stripped = data.strip()
        if stripped in ("Temps de lecture", "Lecture"):
            self._want_reading = True
        elif self._capture_reading and stripped:
            self.reading_time = stripped
            self._capture_reading = False
        if self._body_depth:
            self._body.append(data)

    def body_text(self) -> str:
        return normalize_body("".join(self._body))


def parse_index(html: str, page_url: str = INDEX_URL) -> tuple[list[int], str | None]:
    page = _Page()
    page.feed(html)
    ids = []
    seen = set()
    for href in page.hrefs:
        path = urlparse(urljoin(page_url, href)).path
        match = _FUTUR_PATH.match(path)
        if not match:
            continue
        sid = int(match.group(1))
        if sid in seen:
            continue
        seen.add(sid)
        ids.append(sid)
    nxt = None
    if page.next_href:
        nxt = urljoin(page_url, page.next_href)
    return ids, nxt


def parse_article(html: str) -> dict:
    page = _Page()
    page.feed(html)
    titles = []
    images = []
    author = ""
    published = ""
    for key, content in page.metas:
        if key == "og:title" and content:
            titles.append(content.strip())
        elif key == "og:image" and content:
            images.append(content.strip())
        elif key == "article:author" and content and not author:
            author = content.strip()
        elif key == "article:published_time" and content and not published:
            published = content.strip()
    title = titles[-1] if titles else ""
    if title.startswith("SP2050 - "):
        title = title[len("SP2050 - "):]
    return {
        "title": title,
        "author": author,
        "published_at": published,
        "reading_time": page.reading_time,
        "body": page.body_text(),
        "cover_url": images[-1] if images else "",
        "updated_at": published,
    }


def stories_from_kiosk(payload: dict) -> list[dict]:
    rows = payload.get("futurs")
    if not isinstance(rows, list):
        raise ValueError("futurs")
    stories = []
    for raw in rows:
        if not isinstance(raw, dict) or "id" not in raw:
            continue
        story = {
            "id": int(raw["id"]),
            "title": str(raw.get("title") or "").strip(),
            "author": str(raw.get("author") or "").strip(),
            "published_at": str(raw.get("published_at") or "").strip(),
            "reading_time": str(raw.get("reading_time") or "").strip(),
            "body": normalize_body(str(raw.get("body") or "")),
            "cover_url": str(raw.get("cover_url") or "").strip(),
            "updated_at": str(raw.get("updated_at") or "").strip(),
        }
        story["stamp"] = story_stamp(story)
        stories.append(story)
    return stories


def _default_open(url: str, accept: str):
    req = Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": accept,
        },
    )
    try:
        with urlopen(req, timeout=20) as resp:
            return resp.status, resp.read()
    except HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        return exc.code, body


def _get_text(opener, url: str) -> str:
    status, data = opener(url, "text/html")
    if status != 200:
        raise OSError(f"{status} {url}")
    return data.decode("utf-8", "replace")


def fetch_stories(opener=None) -> list[dict]:
    opener = opener or _default_open
    status, data = opener(KIOSK_URL, "application/json")
    if status == 200 and data:
        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("futurs"), list):
            return stories_from_kiosk(payload)
    return _fetch_html(opener)


def _fetch_html(opener) -> list[dict]:
    ids = []
    seen_pages = set()
    url = INDEX_URL
    for _ in range(20):
        if url in seen_pages:
            break
        seen_pages.add(url)
        page_ids, nxt = parse_index(_get_text(opener, url), url)
        for sid in page_ids:
            if sid not in ids:
                ids.append(sid)
        if not nxt or nxt in seen_pages:
            break
        url = nxt
    stories = []
    for index, sid in enumerate(ids):
        if index:
            time.sleep(0.2)
        try:
            article = parse_article(_get_text(opener, f"{ORIGIN}/futurs/{sid}"))
        except OSError as exc:
            print(f"SP2050 : futur {sid} ignore ({exc}).", flush=True)
            continue
        article["id"] = sid
        article["stamp"] = story_stamp(article)
        stories.append(article)
    return stories


def _lock_file(cache):
    try:
        import fcntl
    except ImportError:
        fcntl = None
    path = cache / ".lock"
    cache.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt

            handle.seek(0)
            if handle.read(1) != b"1":
                handle.seek(0)
                handle.write(b"1")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def _unlock_file(handle):
    if handle is None:
        return
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except ImportError:
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    handle.close()


def sync(cache=None, opener=None) -> bool:
    """Met le cache a jour. Faux si le reseau manque : l'ancien cache reste."""
    root = cache or cache_dir()
    lock = _lock_file(root)
    if lock is None:
        print("SP2050 : synchro deja en cours.", flush=True)
        return False
    try:
        print("SP2050 : synchro.", flush=True)
        try:
            stories = fetch_stories(opener)
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            print(f"SP2050 : pas de reseau ({exc}).", flush=True)
            return False
        if not stories:
            print("SP2050 : liste vide, cache conserve.", flush=True)
            return False
        count = save_library(root, stories, opener or _default_open)
        print(f"SP2050 : {count} futurs en cache.", flush=True)
        return True
    finally:
        _unlock_file(lock)


def main(argv=None):
    del argv
    sync()


if __name__ == "__main__":
    main()
