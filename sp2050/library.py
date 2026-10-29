"""Cache local des futurs. Le reseau n'entre pas ici."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

FIELDS = (
    "id",
    "title",
    "author",
    "published_at",
    "reading_time",
    "body",
    "cover",
    "stamp",
    "updated_at",
)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cache_dir() -> Path:
    return project_root() / "var" / "sp2050"


def catalog_path(cache: Path | None = None) -> Path:
    return (cache or cache_dir()) / "catalog.json"


def normalize_body(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def story_stamp(story: dict) -> str:
    raw = "\n".join(
        [
            str(story.get("title") or ""),
            str(story.get("author") or ""),
            str(story.get("body") or ""),
            str(story.get("cover_url") or ""),
            str(story.get("updated_at") or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def format_date(iso: str) -> str:
    text = (iso or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        year, month, day = text[:4], text[5:7], text[8:10]
        if year.isdigit() and month.isdigit() and day.isdigit():
            return f"{day}.{month}.{year}"
    return ""


@dataclass
class Story:
    id: int
    title: str
    author: str
    published_at: str
    reading_time: str
    body: str
    cover: Path | None
    updated_at: str

    @property
    def when(self) -> str:
        return format_date(self.published_at)


def _read_catalog(cache: Path) -> list[dict]:
    path = catalog_path(cache)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("futurs") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and "id" in row]


def load_stories(cache: Path | None = None) -> list[Story]:
    root = cache or cache_dir()
    stories = []
    for row in _read_catalog(root):
        try:
            sid = int(row["id"])
        except (TypeError, ValueError):
            continue
        cover = None
        rel = row.get("cover") or ""
        if rel:
            path = root / rel
            if path.is_file():
                cover = path
        stories.append(
            Story(
                id=sid,
                title=str(row.get("title") or ""),
                author=str(row.get("author") or ""),
                published_at=str(row.get("published_at") or ""),
                reading_time=str(row.get("reading_time") or ""),
                body=str(row.get("body") or ""),
                cover=cover,
                updated_at=str(row.get("updated_at") or ""),
            )
        )
    return stories


def catalog_mtime(cache: Path | None = None) -> float:
    path = catalog_path(cache)
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def save_library(cache: Path, stories: list[dict], opener=None) -> int:
    """Ecrit le catalogue. Les JPEG deja a jour restent en place.

    Une histoire peut porter `cover_bytes`. Sinon, si `cover_url` est la
    et qu'un opener est fourni, l'image est telechargee. Un echec d'image
    garde l'ancien fichier.
    """
    cache.mkdir(parents=True, exist_ok=True)
    covers = cache / "covers"
    covers.mkdir(exist_ok=True)
    previous = {int(row["id"]): row for row in _read_catalog(cache) if _is_id(row.get("id"))}
    kept = set()
    out = []
    for story in stories:
        sid = int(story["id"])
        name = f"{sid}.jpg"
        dest = covers / name
        stamp = story.get("stamp") or story_stamp(story)
        prev = previous.get(sid)
        same = bool(prev and prev.get("stamp") == stamp and dest.is_file())
        if not same:
            data = story.get("cover_bytes")
            if data is None and story.get("cover_url") and opener is not None:
                data = _fetch_cover(opener, story["cover_url"])
            if data:
                _atomic(dest, data)
        row = {
            "id": sid,
            "title": str(story.get("title") or ""),
            "author": str(story.get("author") or ""),
            "published_at": str(story.get("published_at") or ""),
            "reading_time": str(story.get("reading_time") or ""),
            "body": normalize_body(str(story.get("body") or "")),
            "cover": f"covers/{name}" if dest.is_file() else "",
            "stamp": stamp,
            "updated_at": str(story.get("updated_at") or ""),
        }
        out.append(row)
        kept.add(name)
    for path in covers.glob("*.jpg"):
        if path.name not in kept:
            path.unlink()
    catalog = {
        "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "futurs": out,
    }
    _atomic(
        catalog_path(cache),
        json.dumps(catalog, ensure_ascii=False, indent=2).encode("utf-8"),
    )
    return len(out)


def _is_id(value) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def _fetch_cover(opener, url: str):
    from sp2050.sync import cover_download_url

    try:
        status, data = opener(cover_download_url(url), "image/jpeg")
    except OSError:
        return None
    if status != 200 or not data:
        return None
    return data
