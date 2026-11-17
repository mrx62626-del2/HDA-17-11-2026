# HindiDubAnime API

FastAPI scraper API built around the supplied homepage, anime-details, watch-page and search-page HTML snapshots.

## Features

- Homepage: spotlight, trending, top airing, most popular, completed series, genres, A–Z and What's Hotter.
- Anime details: title, poster, synopsis, metadata, genres, episodes, characters/voice actors, watch link and SEO fields.
- Watch page: episode metadata, player iframe, DUB server choices, previous/next navigation, episode list and anime information.
- In-memory caching, refresh flags, CORS configuration, health endpoint and Swagger docs.
- Optional Cloudflare-aware HTTP client (`cloudscraper`).

## Run locally

Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://127.0.0.1:8000/docs`.

## Main endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | API health |
| GET | `/api/homepage` | Homepage sections |
| GET | `/api/anime/{slug}` | Anime details |
| GET | `/api/anime/{slug}/episodes` | Anime episode catalogue |
| GET | `/api/watch/{slug}` | Complete episode/watch page |
| GET | `/api/watch/{slug}/episodes` | Episode list and navigation |
| GET | `/api/watch/{slug}/servers` | Player servers |
| GET | `/api/watch/{slug}/server/{server_id}` | Resolve a selected server |
| POST | `/api/watch/{slug}/report` | Currently returns 501 until the source AJAX contract is verified |
| GET | `/api/search?q=naruto` | Search anime using the source `s_keyword` query parameter |

Example requests:

```text
GET /api/homepage
GET /api/anime/overgeared-hindi-dubbed
GET /api/watch/overgeared-hindi-dubbed-episode-1
GET /api/watch/overgeared-hindi-dubbed-episode-1/servers
GET /api/watch/overgeared-hindi-dubbed-episode-1/server/cloud
```

Add `?refresh=true` to anime/watch routes to bypass the cached response. Homepage supports `?refresh=true` too.

## Environment variables

- `SOURCE_BASE_URL`: source website base URL.
- `REQUEST_TIMEOUT`: HTTP timeout seconds.
- `CACHE_TTL_SECONDS`: general cache duration.
- `DETAILS_CACHE_TTL_SECONDS`: anime detail cache duration.
- `PLAYER_CACHE_TTL_SECONDS`: reserved player cache setting.
- `CORS_ORIGINS`: comma-separated frontend origins, or `*` for all origins.

## Important source-specific limitations

1. The supplied homepage HTML marks the Latest Hindi Dubbed Anime listing as lazy-loaded. The initial HTML snapshot does not include its loaded cards. The parser returns an empty `latest` array until the source's lazy-load request contract is implemented. If the source responds with a challenge or changed markup, the homepage endpoint now returns HTTP 502 instead of silently returning every section empty.
2. The supplied anime detail page exposes eight episode links while its metadata indicates twelve total episodes. The API reports links actually present in the page; it does not fabricate the missing four. If the site has pagination or a separate episode endpoint, that must be inspected and added.
3. Player choices are iframe embeds, not direct media files. The API returns embed URLs to the frontend. Provider hostnames remain visible in browser network tools; hiding them with base64 or frontend routing is not security.
4. The watch-page HTML exposes the report dialog but not its AJAX action contract, so report submission intentionally returns HTTP 501 instead of guessing. Comments endpoints are not included.
6. Scraping depends on the source website's availability and permission to access it. Use reasonable request rates and cache responses. Do not use this API to bypass access controls or redistribute content without authorization.
7. The parser uses observed selectors from the supplied HTML and may need maintenance if the source theme changes.

## Tests

```bash
pip install pytest
pytest -q
```

The `fixtures/` directory contains the supplied HTML snapshots for parser regression tests. These are test fixtures, not live data.


## Current homepage source path

The supplied WordPress homepage snapshot identifies its canonical URL as `https://hindidubanime.com/homepage/`. The API therefore requests `/homepage/` by default instead of assuming the root `/` is the homepage. Configure `HOMEPAGE_PATH` if the WordPress page URL changes. The parser was tested against `fixtures/homepage-current.html`; the snapshot currently yields 20 spotlight slides, 9 trending slides, 10 Top Airing, 10 Most Popular, 10 Completed Series, 63 genre links, 29 A-Z links, and 10 What's Hotter items. Latest anime is not present in the initial HTML snapshot and remains marked as lazy-loaded/unresolved.

The HTTP client logs response status, final URL, content type, byte count, page title, and redirect status codes to help diagnose source-side access failures. `cloudscraper` is retained as an optional session implementation, but it cannot guarantee access if the origin restricts automated requests. If you own the source site and automated access is being blocked, configure an explicit allow rule at the origin/WAF or provide a supported authenticated API rather than relying on challenge circumvention.
