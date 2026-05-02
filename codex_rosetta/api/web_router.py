from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, Response

# Fix Windows MIME type detection
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/font-woff2", ".woff2")
mimetypes.add_type("application/font-woff", ".woff")

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "dist"

MIME_MAP = {
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "application/font-woff2",
    ".woff": "application/font-woff",
    ".ttf": "font/ttf",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".html": "text/html",
}


def mount_webui(app: FastAPI) -> None:
    """Mount the WebUI SPA and static assets."""
    if not WEB_DIR.exists():
        return

    index = WEB_DIR / "index.html"
    if not index.exists():
        return

    assets_dir = WEB_DIR / "assets"
    if assets_dir.exists():
        app.mount(
            "/app/assets",
            StaticFiles(directory=str(assets_dir)),
            name="web-assets",
        )

    @app.get("/app")
    @app.get("/app/{path:path}")
    async def serve_spa(request: Request, path: str = "") -> Response:
        # Try to serve exact file first
        if path:
            file_path = WEB_DIR / path
            if file_path.is_file():
                ext = file_path.suffix.lower()
                media_type = MIME_MAP.get(ext, "application/octet-stream")
                return FileResponse(str(file_path), media_type=media_type)
        return FileResponse(str(index), media_type="text/html")
