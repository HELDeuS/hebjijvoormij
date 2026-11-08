import os
import re

import requests

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "static", "tool_images")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
SEARCH_TIMEOUT = 10
DOWNLOAD_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def search_image(query):
    """Zoekt een afbeelding via DuckDuckGo Afbeeldingen.

    Geeft de URL van de beste (voldoend grote) afbeelding terug,
    of None als er niets bruikbaars gevonden is.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        landing = session.post(
            "https://duckduckgo.com/", data={"q": query}, timeout=SEARCH_TIMEOUT
        )
        match = re.search(r'vqd=["\']?([\d-]+)["\']?', landing.text)
        if not match:
            return None
        response = session.get(
            "https://duckduckgo.com/i.js",
            params={
                "l": "nl-nl",
                "o": "json",
                "q": query,
                "vqd": match.group(1),
                "f": ",,,",
                "p": "1",
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": "https://duckduckgo.com/",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=SEARCH_TIMEOUT,
        )
        results = response.json().get("results", [])
    except (requests.RequestException, ValueError):
        return None

    for result in results:
        url = result.get("image", "")
        width, height = result.get("width") or 0, result.get("height") or 0
        if url.startswith("http") and width >= 200 and height >= 200:
            return url
    return None


def download_image(image_url, tool_id):
    """Downloadt een afbeelding naar static/tool_images en geeft het relatieve
    pad terug (ten opzichte van de static-map), of None bij mislukking."""
    try:
        response = requests.get(
            image_url, headers=HEADERS, timeout=DOWNLOAD_TIMEOUT, stream=True
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
            return None
        data = response.content
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
    except requests.RequestException:
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


def build_query(name, brand, model):
    parts = [p for p in (brand, model, name) if p]
    return " ".join(parts).strip() or None


def find_and_store_image(tool_id, name, brand, model):
    """Zoekt en slaat een afbeelding op. Geeft het opgeslagen pad terug,
    of None wanneer geen bruikbare afbeelding gevonden is."""
    query = build_query(name, brand, model)
    if not query:
        return None
    image_url = search_image(query)
    if not image_url:
        return None
    return download_image(image_url, tool_id)
