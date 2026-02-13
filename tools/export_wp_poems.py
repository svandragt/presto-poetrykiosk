#!/usr/bin/env python3
"""
Fetch WordPress poems and write /data/poems/<id>.json files.

- Uses WP REST API: /wp-json/wp/v2/posts
- Filename/id: uses the post "slug" (fits your kiosk spec: basename == id)
- JSON schema: {"title": "...", "body": "..."}  (no metadata)

Run (with uv):
  uv run python tools/export_poems.py --out ./data/poems

Notes:
- WordPress returns HTML in content.rendered; we convert to plain text with newlines.
- Title can be empty on your site; we fall back to slug if title is missing/blank.
"""

from __future__ import annotations

import argparse
import json
import re
from html import unescape
from pathlib import Path
from typing import Any, Iterable, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API = "https://poetry.amasan.co.uk/wp-json/wp/v2/posts"
DEFAULT_PER_PAGE = 100  # WP often allows up to 100


WS_RE = re.compile(r"[ \t]+\n")
TRAILING_WS_RE = re.compile(r"[ \t]+$")
MULTI_NL_RE = re.compile(r"\n{3,}")


def http_get_json(url: str) -> Tuple[Any, dict]:
    req = Request(url, headers={"User-Agent": "poetry-kiosk-export/1.0"})
    with urlopen(req, timeout=30) as resp:
        # headers are a mapping-like object
        headers = {k.lower(): v for k, v in resp.headers.items()}
        raw = resp.read()
    return json.loads(raw), headers


def html_to_text(html: str) -> str:
    """
    Minimal HTML -> text for WP post content.
    - Keeps line breaks
    - Removes tags
    - Unescapes entities
    """
    if not html:
        return ""

    s = html

    # Normalize common WP block separators into newlines
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # Convert <br> to newline
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)

    # Put newlines around paragraphs/divs
    s = re.sub(r"(?i)</p\s*>", "\n\n", s)
    s = re.sub(r"(?i)<p\b[^>]*>", "", s)

    s = re.sub(r"(?i)</div\s*>", "\n", s)
    s = re.sub(r"(?i)<div\b[^>]*>", "", s)

    # Strip all remaining tags
    s = re.sub(r"<[^>]+>", "", s)

    # Unescape HTML entities
    s = unescape(s)

    # WP sometimes includes literal "\n" sequences in JSON
    s = s.replace("\\n", "\n")

    # Tidy whitespace (preserve blank lines, but avoid huge runs)
    lines = []
    for line in s.split("\n"):
        line = TRAILING_WS_RE.sub("", line)
        lines.append(line)
    s = "\n".join(lines)
    s = WS_RE.sub("\n", s)
    s = MULTI_NL_RE.sub("\n\n", s).strip()

    return s


def iter_posts(api_base: str, per_page: int) -> Iterable[dict]:
    page = 1
    total_pages = None

    while True:
        url = f"{api_base}?per_page={per_page}&page={page}"
        data, headers = http_get_json(url)

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response shape at page {page}: {type(data)}")

        # WP headers are lowercase here
        if total_pages is None:
            tp = headers.get("x-wp-totalpages")
            if tp:
                try:
                    total_pages = int(tp)
                except ValueError:
                    total_pages = None

        for post in data:
            yield post

        if not data:
            break

        if total_pages is not None and page >= total_pages:
            break

        page += 1


def export_posts(api_base: str, out_dir: Path, per_page: int, overwrite: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    skipped = 0

    for post in iter_posts(api_base, per_page):
        slug = str(post.get("slug", "")).strip()
        if not slug:
            # Fallback: use numeric id if slug is missing
            slug = str(post.get("id", "")).strip()

        if not slug:
            skipped += 1
            print("[export] skip post with no slug and no id")
            continue

        title_html = ""
        title_obj = post.get("title") or {}
        if isinstance(title_obj, dict):
            title_html = str(title_obj.get("rendered", "") or "")

        title = html_to_text(title_html).strip()
        if not title:
            title = slug

        content_obj = post.get("content") or {}
        content_html = ""
        if isinstance(content_obj, dict):
            content_html = str(content_obj.get("rendered", "") or "")

        body = html_to_text(content_html)
        if not body:
            # If content is empty, skip (or keep empty; your kiosk loader allows empty strings)
            print(f"[export] warning: empty body for {slug}")

        payload = {"title": title, "body": body}

        out_path = out_dir / f"{slug}.json"
        if out_path.exists() and not overwrite:
            print(f"[export] exists, skipping: {out_path.name}")
            skipped += 1
            continue

        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        count += 1

    print(f"[export] wrote {count} poem files to {out_dir} (skipped {skipped})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=DEFAULT_API, help="WP posts endpoint")
    ap.add_argument("--out", required=True, help="Output directory for poem JSON files")
    ap.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE, help="WP per_page (try 100)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = ap.parse_args()

    try:
        export_posts(args.api, Path(args.out), args.per_page, args.overwrite)
    except HTTPError as e:
        print(f"[export] HTTP error: {e.code} {e.reason}")
        raise SystemExit(2)
    except URLError as e:
        print(f"[export] Network error: {e}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
