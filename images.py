import io
import os
import re

import requests

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "static", "tool_images")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
DOWNLOAD_TIMEOUT = 15

def _log(message):
    """Logt direct naar stdout met flush, zodat regels meteen in
    journalctl verschijnen (stdout is onder systemd gebufferd)."""
    print(message, flush=True)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def download_image(image_url, tool_id):
    """Downloadt een afbeelding van een URL naar static/tool_images en
    geeft het relatieve pad terug, of None bij mislukking. Het bestand
    wordt gevalideerd op type (jpg, png, webp, gif), afmetingen
    (minimaal 200x200) en grootte (max. 5 MB) en op de server bewaard."""
    try:
        response = requests.get(
            image_url, headers=HEADERS, timeout=DOWNLOAD_TIMEOUT
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        extensions = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        if content_type not in extensions:
            _log(f"plaatjes: url {image_url} heeft onbekend type {content_type}")
            return None
        data = response.content
        if not data or len(data) > MAX_IMAGE_BYTES:
            _log(f"plaatjes: url {image_url} is leeg of te groot")
            return None
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as img:
                if img.width < 200 or img.height < 200:
                    _log(f"plaatjes: url {image_url} is te klein ({img.width}x{img.height})")
                    return None
        except Exception:
            _log(f"plaatjes: url {image_url} is geen geldige afbeelding")
            return None
        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = f"tool_{tool_id}{extensions[content_type]}"
        for old in os.listdir(IMAGES_DIR):
            if old.startswith(f"tool_{tool_id}."):
                os.remove(os.path.join(IMAGES_DIR, old))
        with open(os.path.join(IMAGES_DIR, filename), "wb") as f:
            f.write(data)
        return f"tool_images/{filename}"
    except requests.RequestException as exc:
        _log(f"plaatjes: download van {image_url} faalde: {exc}")
        return None


def upload_image(file_storage, tool_id):
    """Slaat een geüpload afbeeldingsbestand op naar static/tool_images en
    geeft het relatieve pad terug, of None bij een ongeldig bestand."""
    if not file_storage or not file_storage.filename:
        return None
    content_type = file_storage.content_type or ""
    extensions = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if content_type not in extensions:
        return None
    data = file_storage.read()
    if not data or len(data) > MAX_IMAGE_BYTES:
        return None
    os.makedirs(IMAGES_DIR, exist_ok=True)
    filename = f"tool_{tool_id}{extensions[content_type]}"
    for old in os.listdir(IMAGES_DIR):
        if old.startswith(f"tool_{tool_id}."):
            os.remove(os.path.join(IMAGES_DIR, old))
    with open(os.path.join(IMAGES_DIR, filename), "wb") as f:
        f.write(data)
    return f"tool_images/{filename}"
