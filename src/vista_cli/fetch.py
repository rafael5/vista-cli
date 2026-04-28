"""Network fetch + install of snapshot bundles.

Reads URLs (`http://`, `https://`, `file://`) or bare paths, downloads
to a cache dir, and installs atomically via `snapshot.install_bundle`.
The download is a thin wrapper around `urllib` so tests can run
against `file://` URLs without network.
"""

from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from vista_cli.snapshot import (
    SnapshotError,
    install_bundle,
)

DEFAULT_RELEASES_API = (
    "https://api.github.com/repos/rafael5/vista-cli/releases"
)


class FetchError(Exception):
    """Raised on download / verify / install failures during fetch."""


# ── Download primitive ────────────────────────────────────────────


def download_to(url: str, dest: Path) -> None:
    """Stream `url` (HTTP, HTTPS, file://, or a bare path) to `dest`.

    Raises `FetchError` on any failure. The destination file is
    written atomically (`<dest>.partial` then renamed).
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")

    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme:
        # bare path
        url = Path(url).resolve().as_uri()

    try:
        with urllib.request.urlopen(url) as resp, tmp.open("wb") as out:
            shutil.copyfileobj(resp, out)
    except (urllib.error.URLError, OSError, ValueError) as e:
        if tmp.exists():
            tmp.unlink()
        raise FetchError(f"download failed: {e}") from e

    tmp.rename(dest)


# ── End-to-end fetch + install ────────────────────────────────────


def fetch_and_install(
    *,
    url: str,
    data_dir: Path,
    cache_dir: Path,
) -> dict[str, Any]:
    """Download, verify, and install a bundle.

    Existing data at `data_dir` is left intact until the new bundle
    verifies; on success it is moved to `data_dir.bak/` and the new
    bundle takes its place.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Use the URL's basename as the cache filename (stable across reruns)
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or "snapshot.tar.xz"
    bundle_path = cache_dir / name

    try:
        download_to(url, bundle_path)
    except FetchError:
        raise
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"download failed: {e}") from e

    try:
        return install_bundle(bundle=bundle_path, data_dir=data_dir)
    except SnapshotError as e:
        raise FetchError(f"install failed: {e}") from e


# ── GitHub releases listing ───────────────────────────────────────


def list_remote_snapshots(
    *, releases_api: str = DEFAULT_RELEASES_API
) -> list[dict[str, Any]]:
    """Query the GitHub Releases API for available snapshots.

    Returns a list of `{version, tag, url, size, published_at}` dicts,
    most recent first. Filters releases whose tag starts with
    `snapshot-`.
    """
    try:
        with urllib.request.urlopen(releases_api) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise FetchError(f"could not query releases API: {e}") from e
    return parse_release_listing(payload)


def parse_release_listing(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pure helper — extract snapshot rows from a GitHub releases payload."""
    out: list[dict[str, Any]] = []
    for rel in payload:
        tag = rel.get("tag_name", "")
        if not tag.startswith("snapshot-"):
            continue
        version = tag.removeprefix("snapshot-")
        for asset in rel.get("assets", []):
            name = asset.get("name", "")
            if not name.endswith(".tar.xz"):
                continue
            out.append(
                {
                    "version": version,
                    "tag": tag,
                    "url": asset.get("browser_download_url", ""),
                    "size": asset.get("size", 0),
                    "published_at": rel.get("published_at", ""),
                }
            )
            break
    return out
