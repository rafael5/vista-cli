"""Tests for vista fetch — download + verify + atomic install.

Uses file:// URLs against a local fixture bundle so the tests don't
need network. The fetch logic itself is HTTP-agnostic (it accepts a
URL or a Path) so the same code path is exercised either way.
"""

from pathlib import Path

import pytest

from vista_cli.fetch import (
    FetchError,
    download_to,
    fetch_and_install,
    parse_release_listing,
)
from vista_cli.snapshot import create_bundle

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def published_bundle(tmp_path):
    """Create a bundle on disk and expose it as a file:// URL."""
    out = tmp_path / "vista-snapshot-2026.04.28.tar.xz"
    create_bundle(
        out=out,
        code_model_dir=FIXTURES / "code-model",
        data_model_dir=FIXTURES / "data-model",
        doc_db=FIXTURES / "frontmatter.db",
        snapshot_version="2026.04.28",
    )
    return out


class TestDownloadTo:
    def test_download_file_url(self, published_bundle, tmp_path):
        url = published_bundle.as_uri()
        dest = tmp_path / "downloaded.tar.xz"
        download_to(url, dest)
        assert dest.exists()
        assert dest.read_bytes() == published_bundle.read_bytes()

    def test_download_local_path(self, published_bundle, tmp_path):
        dest = tmp_path / "downloaded.tar.xz"
        download_to(str(published_bundle), dest)
        assert dest.read_bytes() == published_bundle.read_bytes()

    def test_download_missing_url_raises(self, tmp_path):
        bogus = (tmp_path / "nope.tar.xz").as_uri()
        with pytest.raises(FetchError):
            download_to(bogus, tmp_path / "dest.tar.xz")


class TestFetchAndInstall:
    def test_end_to_end(self, published_bundle, tmp_path):
        data_dir = tmp_path / "data"
        manifest = fetch_and_install(
            url=published_bundle.as_uri(),
            data_dir=data_dir,
            cache_dir=tmp_path / "cache",
        )
        assert (data_dir / "snapshot.json").exists()
        assert (data_dir / "frontmatter.db").exists()
        assert manifest["snapshot_version"] == "2026.04.28"

    def test_atomic_swap_preserves_old(self, published_bundle, tmp_path):
        data_dir = tmp_path / "data"
        cache_dir = tmp_path / "cache"
        fetch_and_install(
            url=published_bundle.as_uri(),
            data_dir=data_dir,
            cache_dir=cache_dir,
        )
        first_manifest = (data_dir / "snapshot.json").read_bytes()
        # Second fetch — same content, but should still complete and
        # leave a `.bak/` of the previous install.
        fetch_and_install(
            url=published_bundle.as_uri(),
            data_dir=data_dir,
            cache_dir=cache_dir,
        )
        bak = data_dir.parent / (data_dir.name + ".bak")
        assert bak.exists()
        assert (bak / "snapshot.json").read_bytes() == first_manifest

    def test_corrupted_download_does_not_clobber(
        self, published_bundle, tmp_path
    ):
        # Pre-existing install
        data_dir = tmp_path / "data"
        cache_dir = tmp_path / "cache"
        fetch_and_install(
            url=published_bundle.as_uri(),
            data_dir=data_dir,
            cache_dir=cache_dir,
        )
        original = (data_dir / "snapshot.json").read_bytes()

        # Now point at a corrupted "bundle" — the fetch should fail and
        # the existing install should be untouched.
        bad = tmp_path / "bad.tar.xz"
        bad.write_bytes(b"not a tar file")
        with pytest.raises(FetchError):
            fetch_and_install(
                url=bad.as_uri(),
                data_dir=data_dir,
                cache_dir=cache_dir,
            )
        assert (data_dir / "snapshot.json").read_bytes() == original


class TestParseReleaseListing:
    def test_parses_github_release_payload(self):
        payload = [
            {
                "tag_name": "snapshot-2026.04.28",
                "published_at": "2026-04-28T15:00:00Z",
                "assets": [
                    {
                        "name": "vista-snapshot-2026.04.28.tar.xz",
                        "browser_download_url": (
                            "https://github.com/x/y/releases/download/"
                            "snapshot-2026.04.28/vista-snapshot-2026.04.28.tar.xz"
                        ),
                        "size": 60_123_456,
                    },
                    {
                        "name": "vista-snapshot-2026.04.28.tar.xz.sha256",
                        "browser_download_url": "...",
                        "size": 100,
                    },
                ],
            },
            {
                "tag_name": "v0.3.0",  # non-snapshot tag — must be filtered
                "assets": [],
            },
        ]
        snapshots = parse_release_listing(payload)
        assert len(snapshots) == 1
        assert snapshots[0]["version"] == "2026.04.28"
        assert snapshots[0]["tag"] == "snapshot-2026.04.28"
        assert snapshots[0]["url"].endswith(".tar.xz")
        assert snapshots[0]["size"] == 60_123_456
