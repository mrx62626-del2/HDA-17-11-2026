from pathlib import Path
from app.parsers import parse_homepage, parse_anime, parse_watch

ROOT = Path(__file__).resolve().parents[1]

def read(name):
    return (ROOT / "fixtures" / name).read_text(encoding="utf-8", errors="ignore")

def test_homepage_parser():
    data = parse_homepage(read("homepage.html"))
    assert len(data["spotlight"]) > 0
    assert len(data["trending"]) > 0
    assert len(data["genres"]) > 0
    assert len(data["az_list"]) > 0
    assert len(data["top_airing"]) > 0
    assert len(data["most_popular"]) > 0
    assert len(data["completed_series"]) > 0

def test_anime_parser():
    data = parse_anime(read("anime.html"), "https://hindidubanime.com/anime/overgeared-hindi-dubbed/")
    assert data["id"] == 7758
    assert data["slug"] == "overgeared-hindi-dubbed"
    assert data["title"]
    assert data["poster"].startswith("https://")
    assert [g["name"] for g in data["genres"]] == ["Action", "Adventure", "Comedy", "Fantasy"]
    assert data["episodes"]
    assert data["characters"]

def test_watch_parser():
    data = parse_watch(read("watch.html"), "https://hindidubanime.com/watch/overgeared-hindi-dubbed-episode-1/")
    assert data["id"] == 7762
    assert data["number"] == 1
    assert data["anime"]["id"] == 7758
    assert len(data["player"]["servers"]) == 3
    assert data["navigation"]["next"]["url"].endswith("episode-2/")
    assert len(data["episode_list"]) == 8

def test_search_parser():
    from app.parsers import parse_search
    data = parse_search(read("search-naruto.html"), "https://hindidubanime.com/search/?s_keyword=naruto", "naruto")
    assert data["query"] == "naruto"
    assert data["count"] == 4
    assert any("naruto-season-1" in item["slug"] for item in data["results"])
    assert all(item["poster"] for item in data["results"])

def test_homepage_rejects_non_homepage_html():
    import pytest
    with pytest.raises(ValueError, match="did not return"):
        parse_homepage("<html><body>challenge page</body></html>")

def test_homepage_endpoint_returns_parsed_sections(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app, source
    html = read("homepage.html")
    monkeypatch.setattr(source, "get_html", lambda url: (html, "https://hindidubanime.com/"))
    response = TestClient(app).get("/api/homepage?refresh=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data["spotlight"]) > 0
    assert len(data["top_airing"]) > 0
    assert len(data["genres"]) > 0


def test_current_uploaded_homepage_snapshot():
    data = parse_homepage(read("homepage-current.html"), "https://hindidubanime.com/homepage/")
    assert len(data["spotlight"]) == 20
    assert len(data["trending"]) == 9
    assert len(data["top_airing"]) == 10
    assert len(data["most_popular"]) == 10
    assert len(data["completed_series"]) == 10
    assert len(data["genres"]) > 0


def test_homepage_endpoint_requests_configured_homepage_path(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app, source
    from app.config import HOMEPAGE_PATH
    html = read("homepage-current.html")
    requested = {}
    def fake_get_html(url):
        requested["url"] = url
        return html, "https://hindidubanime.com/homepage/"
    monkeypatch.setattr(source, "get_html", fake_get_html)
    response = TestClient(app).get("/api/homepage?refresh=true")
    assert response.status_code == 200
    assert requested["url"] == HOMEPAGE_PATH == "/homepage/"
    assert len(response.json()["spotlight"]) == 20
