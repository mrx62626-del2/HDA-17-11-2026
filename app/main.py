from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from app.client import source, SourceError
from app.config import BASE_URL, HOMEPAGE_PATH, CACHE_TTL, DETAILS_CACHE_TTL, PLAYER_CACHE_TTL, CORS_ORIGINS
from app.cache import get, set_value
from app.parsers import parse_homepage, parse_anime, parse_watch, parse_search
import re

app = FastAPI(title="HindiDubAnime API", version="1.1.0", description="Read-only scraper API for homepage, anime details and episode watch pages.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
                   allow_credentials=CORS_ORIGINS != ["*"], allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])

def valid_slug(slug: str):
    if not re.fullmatch(r"[a-zA-Z0-9-]{1,180}", slug):
        raise HTTPException(400, "Invalid slug")
    return slug

def fetch_parsed(key, url, parser, ttl=CACHE_TTL):
    cached = get(key)
    if cached is not None: return cached
    try:
        html, final_url = source.get_html(url)
        data = parser(html, final_url)
        set_value(key, data, ttl)
        return data
    except SourceError as exc:
        raise HTTPException(502, str(exc))
    except ValueError as exc:
        raise HTTPException(502, str(exc))

@app.get("/")
def root():
    return {"name": "HindiDubAnime API", "version": "1.0.0", "status": "running", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health():
    return {"status": "ok", "source": BASE_URL}

@app.get("/api/homepage")
def homepage(refresh: bool = Query(False, description="Bypass cached response")):
    if refresh:
        from app.cache import clear
        clear()
    return fetch_parsed("homepage", HOMEPAGE_PATH, parse_homepage, CACHE_TTL)

@app.get("/api/anime/{slug}")
def anime_details(slug: str, refresh: bool = False):
    slug = valid_slug(slug)
    return fetch_parsed(f"anime:{slug}", f"/anime/{slug}/", parse_anime, DETAILS_CACHE_TTL) if not refresh else _refresh_parse(f"anime:{slug}", f"/anime/{slug}/", parse_anime)

def _refresh_parse(key, url, parser):
    try:
        html, final_url = source.get_html(url)
        data = parser(html, final_url)
        set_value(key, data, DETAILS_CACHE_TTL)
        return data
    except SourceError as exc:
        raise HTTPException(502, str(exc))

@app.get("/api/anime/{slug}/episodes")
def anime_episodes(slug: str):
    data = anime_details(slug)
    return {"anime": {"slug": data.get("slug"), "title": data.get("title")}, "episodes": data.get("episodes", [])}

@app.get("/api/watch/{slug}")
def watch_page(slug: str, refresh: bool = False):
    slug = valid_slug(slug)
    url = f"/watch/{slug}/"
    if refresh: return _refresh_parse(f"watch:{slug}", url, parse_watch)
    return fetch_parsed(f"watch:{slug}", url, parse_watch, PLAYER_CACHE_TTL)

@app.get("/api/watch/{slug}/episodes")
def watch_episodes(slug: str):
    data = watch_page(slug)
    return {"anime": data.get("anime"), "current_episode": data.get("number"), "navigation": data.get("navigation"), "episodes": data.get("episode_list", [])}

@app.get("/api/watch/{slug}/servers")
def watch_servers(slug: str):
    data = watch_page(slug)
    return {"episode": data.get("slug"), "default_server": data.get("player", {}).get("default_server"), "servers": data.get("player", {}).get("servers", [])}

@app.get("/api/watch/{slug}/server/{server_id}")
def resolve_server(slug: str, server_id: str):
    data = watch_page(slug)
    for server in data.get("player", {}).get("servers", []):
        if server["id"] == server_id:
            return {"episode": slug, "server": server}
    raise HTTPException(404, "Server not found for this episode")

@app.post("/api/watch/{slug}/report")
def report_problem(slug: str, request: Request):
    # The source HTML exposes the report dialog but not the AJAX action contract.
    # Avoid inventing a backend action; return a clear unsupported response.
    raise HTTPException(501, "The source report endpoint is not exposed in the supplied page HTML. Configure the source site's report AJAX action before enabling this feature.")


@app.get("/api/search")
def search_anime(q: str | None = Query(default=None, min_length=1, max_length=100),
                 s_keyword: str | None = Query(default=None, min_length=1, max_length=100)):
    query = (q or s_keyword or "").strip()
    if not query:
        raise HTTPException(400, "Provide a search term using q or s_keyword")
    # The source search page uses the GET parameter s_keyword.
    from urllib.parse import urlencode
    url = "/search/?" + urlencode({"s_keyword": query})
    key = f"search:{query.casefold()}"
    return fetch_parsed(key, url, lambda html, final_url: parse_search(html, final_url, query), DETAILS_CACHE_TTL)
