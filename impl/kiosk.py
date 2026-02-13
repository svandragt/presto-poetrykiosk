# impl/kiosk.py

import os
import ujson


def _is_json(name: str) -> bool:
    return name.endswith(".json") and len(name) > 5


def _basename_no_ext(name: str) -> str:
    # "foo.json" -> "foo"
    return name[:-5]


def build_playlist(
    poems_dir: str = "/data/poems",
    photos_dir: str = "/data/photos",
) -> list[str]:
    """
    Scan poems_dir for *.json and include only ids that have a matching
    photos_dir/<id>.jpg.

    Returns a sorted list of poem ids (deterministic base order).
    """
    try:
        entries = os.listdir(poems_dir)
    except OSError as e:
        print(f"[kiosk] cannot list poems dir {poems_dir}: {e}")
        return []

    ids: list[str] = []

    for name in entries:
        if not _is_json(name):
            continue

        poem_id = _basename_no_ext(name)
        photo_path = f"{photos_dir}/{poem_id}.jpg"

        try:
            os.stat(photo_path)
        except OSError:
            # Spec: skip poem if photo missing
            print('missing photo:' + photo_path)
            # continue

        ids.append(poem_id)

    ids.sort()
    return ids


def load_poem(
    poem_id: str,
    poems_dir: str = "/data/poems",
) -> dict | None:
    """
    Load and validate a single poem JSON.

    Required keys:
      - title: str
      - body: str

    Returns {"title": str, "body": str} or None on error.
    """
    path = f"{poems_dir}/{poem_id}.json"

    try:
        with open(path, "r") as f:
            data = ujson.load(f)
    except OSError as e:
        print(f"[kiosk] cannot open {path}: {e}")
        return None
    except ValueError as e:
        # ujson parse error
        print(f"[kiosk] invalid JSON in {path}: {e}")
        return None

    if not isinstance(data, dict):
        print(f"[kiosk] JSON root must be an object in {path}")
        return None

    title = data.get("title")
    body = data.get("body")

    if not isinstance(title, str) or not isinstance(body, str):
        print(f"[kiosk] invalid schema in {path}: title/body must be strings")
        return None

    return {
        "title": title,
        "body": body,
    }
