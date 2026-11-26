"""Cache headers for the built web UI: index.html revalidates, hashed assets don't."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zoomify.api.app import ASSET_CACHE_CONTROL, mount_frontend


@pytest.fixture
def spa(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    app = FastAPI()
    mount_frontend(app, tmp_path)
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/pricing", "/sign-in/factor-one", "/favicon.svg"])
def test_html_and_public_files_are_revalidated(spa, path):
    res = spa.get(path)
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_cached_forever(spa):
    res = spa.get("/assets/index-abc123.js")
    assert res.status_code == 200
    assert res.headers["cache-control"] == ASSET_CACHE_CONTROL
    assert "immutable" in ASSET_CACHE_CONTROL


def test_missing_asset_is_an_uncached_404_not_index_html(spa):
    res = spa.get("/assets/index-old999.js")
    assert res.status_code == 404
    assert "cache-control" not in res.headers
