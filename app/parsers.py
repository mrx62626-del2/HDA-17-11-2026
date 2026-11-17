import base64
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from app.config import BASE_URL


def clean(node):
    return node.get_text(" ", strip=True) if node else None

def absolute(url, base=BASE_URL):
    return urljoin(base + "/", url) if url else None

def slug_from_url(url):
    if not url: return None
    return urlparse(url).path.rstrip("/").split("/")[-1] or None

def image_of(node):
    if not node: return None
    img = node.select_one("img") if node.name != "img" else node
    if not img: return None
    return absolute(img.get("data-src") or img.get("data-lazy-src") or img.get("src"))

def anime_card(node):
    a = node if node.name == "a" and "/anime/" in (node.get("href") or "") else node.select_one('a[href*="/anime/"]')
    if not a: return None
    title_node = a.select_one("[data-nt-title]") or a.select_one("[data-en-title]") or a.select_one("h3,h2")
    title = clean(title_node) or a.get("title")
    if not title: title = a.get("title")
    if not title: return None
    img = a.select_one("img") or node.select_one("img")
    info = clean(node.select_one(".anime-card-info,.anime-metadata,.text-spec"))
    return {"title": title, "url": absolute(a.get("href")), "slug": slug_from_url(a.get("href")),
            "poster": image_of(img) if img else None, "metadata": info}

def _cards_in(container):
    """Extract distinct anime cards from a known section/container."""
    cards, seen = [], set()
    for a in container.select('a[href*="/anime/"]'):
        url = absolute(a.get("href"))
        if not url or url in seen:
            continue
        card = anime_card(a)
        if not card:
            continue
        # The poster often sits in a sibling visual wrapper, not inside the title link.
        visual = a.find_parent(class_=re.compile(r"kira-anime"))
        if visual and not card.get("poster"):
            card["poster"] = image_of(visual)
        if visual:
            card["metadata"] = clean(visual.parent)
        cards.append(card)
        seen.add(url)
    return cards


def parse_homepage(html, page_url=BASE_URL):
    soup = BeautifulSoup(html, "html.parser")
    body_classes = soup.body.get("class", []) if soup.body else []
    # Avoid silently caching a Cloudflare/challenge/error page as a valid empty homepage.
    if not soup.select_one("main") or not soup.select_one(".ks-hero, .ks-hero__slide, .kira-grid-featured"):
        raise ValueError("Source did not return the HindiDubAnime homepage HTML. It may be a Cloudflare challenge, an error page, or a changed source template.")

    hero, seen_hero = [], set()
    for slide in soup.select(".ks-hero .swiper-spotlight .ks-hero__slide, .ks-hero__slide"):
        a = slide.select_one('a[href*="/anime/"]')
        title = clean(slide.select_one(".ks-hero__title")) or (a.get("title") if a else None)
        if not title:
            continue
        url = absolute(a.get("href")) if a else None
        if url and url in seen_hero:
            continue
        hero.append({"title": title, "url": url, "slug": slug_from_url(a.get("href")) if a else None,
                     "poster": image_of(slide.select_one(".ks-hero__img")) or image_of(slide),
                     "description": clean(slide.select_one(".ks-hero__description,.ks-hero__desc")),
                     "meta": clean(slide.select_one(".ks-hero__meta"))})
        if url: seen_hero.add(url)

    trending = []
    for slide in soup.select(".swiper-trending .swiper-slide"):
        card = anime_card(slide)
        if card:
            card["poster"] = card.get("poster") or image_of(slide)
            trending.append(card)

    sections = {"top_airing": [], "most_popular": [], "completed_series": []}
    wanted = {"top airing!": "top_airing", "top airing": "top_airing",
              "most popular": "most_popular", "completed series": "completed_series"}
    for heading in soup.select("main h2, main h3"):
        key = wanted.get((clean(heading) or "").casefold())
        if not key:
            continue
        section = heading.find_parent("section")
        if section:
            sections[key] = _cards_in(section)

    latest = []
    listing = soup.select_one('[data-component-name="listing"]')
    if listing:
        latest = _cards_in(listing)
    if not latest:
        latest_container = soup.select_one(".latest-anime, #latest-anime, [data-latest-anime]")
        if latest_container:
            latest = _cards_in(latest_container)

    genres = [{"name": clean(a), "url": absolute(a.get("href")), "slug": slug_from_url(a.get("href"))}
              for a in soup.select(".genre-list a") if clean(a)]
    az = [{"label": clean(x), "url": absolute(x.get("data-alphabet-link"))}
          for x in soup.select("[data-alphabet-link]") if clean(x)]
    hotter = []
    for li in soup.select("ul.bg-overlay > li"):
        card = anime_card(li)
        if card: hotter.append(card)

    result = {"source": page_url, "spotlight": hero, "trending": trending,
              "latest": latest, "top_airing": sections["top_airing"],
              "most_popular": sections["most_popular"],
              "completed_series": sections["completed_series"],
              "genres": genres, "az_list": az, "whats_hotter": hotter,
              "notes": []}
    # An authentic homepage has static navigation/genre data even when the Latest
    # section is client-loaded. Empty arrays across the board indicate a bad fetch.
    if not any(result[k] for k in ("spotlight", "trending", "top_airing", "most_popular", "completed_series", "genres", "az_list", "whats_hotter")):
        raise ValueError("HindiDubAnime homepage was retrieved but no known homepage sections were found. The source markup may have changed.")
    if not latest:
        result["notes"].append("Latest anime is client/lazy-loaded and is not present in the supplied initial HTML; its source request has not yet been identified.")
    return result


def parse_search(html, page_url, query):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main")
    if not main or "page-template-search" not in (soup.body.get("class", []) if soup.body else []):
        raise ValueError("Search request did not return the HindiDubAnime search-results page. Check source access or the search URL.")

    results, seen = [], set()
    # In the supplied search HTML each result is a .kira-anime visual card followed
    # by a separate title link in the same outer card wrapper.
    for visual in main.select(".kira-anime"):
        wrapper = visual.parent
        links = wrapper.select('a[href*="/anime/"]')
        title_link = next((a for a in links if clean(a)), None)
        if not title_link:
            continue
        url = absolute(title_link.get("href"))
        if not url or url in seen:
            continue
        title_node = title_link.select_one("[data-nt-title]") or title_link.select_one("[data-en-title]")
        title = clean(title_node) or clean(title_link)
        if not title:
            continue
        image = image_of(visual)
        badge = clean(visual.select_one(".bg-accent-3"))
        status = clean(visual.select_one(".status_show"))
        meta = clean(wrapper.select_one(".text-xs"))
        results.append({"title": title, "url": url, "slug": slug_from_url(url),
                        "poster": image, "episode": badge, "status": status,
                        "metadata": meta})
        seen.add(url)

    if not results and not main.select_one("#advanced-search"):
        raise ValueError("Search results could not be parsed from the source response; the source template may have changed.")

    pagination = []
    for a in main.select(".pagination a, .page-numbers a, a[rel='next'], a[rel='prev']"):
        href = absolute(a.get("href"))
        if href:
            pagination.append({"label": clean(a), "url": href})
    return {"query": query, "source": page_url, "count": len(results), "results": results,
            "pagination": pagination, "has_more": any("next" in (x.get("label") or "").lower() or "next" in x["url"].lower() for x in pagination),
            "notes": [] if results else ["No matching anime cards were present in the returned search page."]}


def _label_value(soup, label):
    for li in soup.select("section ul li"):
        spans = li.find_all("span", recursive=False)
        if len(spans) >= 2 and clean(spans[0]).rstrip(":").lower() == label.lower():
            return clean(spans[1])
    return None

def parse_anime(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("h1")
    title = clean(soup.select_one("[data-nt-title]")) or clean(h1)
    english = clean(soup.select_one("[data-en-title]"))
    poster = None
    for q in [".anime-image img", ".anime-featured img", ".anime-poster img", ".anime-cover img"]:
        poster = image_of(soup.select_one(q))
        if poster: break
    banner = None
    for q in [".anime-banner img", ".anime-cover-bg img", ".anime-background img"]:
        banner = image_of(soup.select_one(q))
        if banner: break
    if not banner:
        for candidate in soup.select("img[src]"):
            src = candidate.get("src", "")
            if "storyblok" in src:
                banner = absolute(src)
                break
    if not banner:
        bg = soup.select_one(".background-image[style]")
        if bg:
            match = re.search(r"url\([\"']?(.*?)[\"']?\)", bg.get("style", ""))
            if match: banner = absolute(match.group(1))
    metadata = [clean(x) for x in soup.select(".anime-metadata li") if clean(x)]
    synopsis = clean(soup.select_one("[data-synopsis]")) or clean(soup.select_one(".anime-synopsis"))
    trailer = None
    for script in soup.find_all("script"):
        txt = script.string or script.get_text()
        match = re.search(r"openVideoEmbed\(['\"]([^'\"]+)", txt or "")
        if match: trailer = match.group(1); break
    first_watch = None
    eps = []
    for slide in soup.select(".swiper-episode-anime .swiper-slide"):
        a = slide.select_one('a[href*="/watch/"]')
        if not a: continue
        ep_title = a.get("title") or clean(a)
        ep_num_match = re.search(r"(?:episode|ep)\s*(\d+(?:\.\d+)?)", ep_title or "", re.I)
        eps.append({"title": ep_title, "number": float(ep_num_match.group(1)) if ep_num_match else None,
                    "url": absolute(a.get("href")), "slug": slug_from_url(a.get("href")), "thumbnail": image_of(a)})
    if eps: first_watch = next((x["url"] for x in eps if x["number"] == 1), eps[-1]["url"])
    genres = []
    studios = []
    for li in soup.select("section ul li"):
        spans = li.find_all("span", recursive=False)
        if len(spans) < 2: continue
        label = clean(spans[0]).rstrip(":").lower()
        target = genres if label in ("genre", "genres") else studios if label in ("studio", "studios") else None
        if target is not None:
            for a in spans[1].select("a"):
                item = {"name": clean(a), "url": absolute(a.get("href"))}
                if item["name"] and item not in target: target.append(item)
    characters = []
    for item in soup.select("[data-characters] [data-character]"):
        cols = item.select(":scope > div")
        imgs = item.select("img")
        links = item.select("a")
        characters.append({"name": clean(links[0]) if links else clean(item),
                           "image": image_of(imgs[0]) if imgs else None,
                           "role": clean(item.select_one(".character-role,.text-xs")),
                           "voice_actor": clean(links[-1]) if len(links) > 1 else None,
                           "voice_actor_image": image_of(imgs[-1]) if len(imgs) > 1 else None})
    add_list = soup.select_one("[data-anime-tippy-add-list]")
    postid = None
    if soup.body:
        for c in soup.body.get("class", []):
            m = re.match(r"postid-(\d+)", c)
            if m: postid = int(m.group(1))
    sidebar = {}
    for key in ["Premiered", "Rate", "Native", "English", "Synonyms", "Aired", "Duration", "Episodes", "Score", "Genres", "Studio", "Status"]:
        val = _label_value(soup, key)
        if val: sidebar[key.lower()] = val
    return {"id": postid, "slug": slug_from_url(page_url), "url": page_url,
            "title": title, "english_title": english, "poster": poster, "banner": banner,
            "metadata": metadata, "synopsis": synopsis, "trailer": trailer,
            "genres": genres, "studios": studios, "sidebar": sidebar, "episodes": eps,
            "latest_episode": max([x["number"] for x in eps if x["number"] is not None], default=None),
            "watch_now": first_watch, "characters": characters,
            "add_to_list_id": add_list.get("data-anime-tippy-add-list") if add_list else None,
            "seo": {"title": clean(soup.title), "description": (soup.select_one('meta[name="description"]') or {}).get("content"),
                    "canonical_url": (soup.select_one('link[rel="canonical"]') or {}).get("href")}}


def _decode_server(encoded):
    try:
        a, b = encoded.split(":", 1)
        label = base64.b64decode(a + "==").decode("utf-8", "ignore")
        url = base64.b64decode(b + "==").decode("utf-8", "ignore")
        return label, url
    except Exception:
        return None, None

def parse_watch(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    body_classes = soup.body.get("class", []) if soup.body else []
    post_id = next((int(m.group(1)) for c in body_classes if (m := re.match(r"postid-(\d+)", c))), None)
    current = soup.select_one(".episode-list-item.current-episode")
    current_num = None
    if current:
        try: current_num = int(current.get("data-episode-search-query"))
        except (TypeError, ValueError): pass
    if current_num is None:
        m = re.search(r"episode-(\d+)", page_url)
        current_num = int(m.group(1)) if m else None
    anime_link = soup.select_one('.episode-anime-info a[href*="/anime/"]')
    anime_id = None
    watchlist = soup.select_one("[data-tippy-sub-trigger]")
    if watchlist:
        try: anime_id = int(watchlist.get("data-tippy-sub-trigger"))
        except ValueError: pass
    iframe = soup.select_one(".episode-player-box iframe")
    servers = []
    for el in soup.select(".player-dub [data-embed-id], .player-sub [data-embed-id]"):
        label, embed = _decode_server(el.get("data-embed-id", ""))
        if not label: continue
        servers.append({"id": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"),
                        "label": clean(el), "language": "Hindi" if "dub" in label.lower() else "Unknown",
                        "type": "embed", "available": True, "default": "active" in el.get("class", []),
                        "embed_url": embed})
    episodes = []
    for a in soup.select(".episode-list-item[href*='/watch/']"):
        num = a.get("data-episode-search-query")
        try: num = int(num)
        except (ValueError, TypeError): num = None
        episodes.append({"number": num, "title": clean(a.select_one(".episode-list-item-title")) or clean(a),
                         "url": absolute(a.get("href")), "slug": slug_from_url(a.get("href")),
                         "current": "current-episode" in a.get("class", [])})
    prev_el = soup.select_one(".previous-episode[data-open-nav-episode]")
    next_el = soup.select_one(".next-episode[data-open-nav-episode]")
    def nav(el):
        u = el.get("data-open-nav-episode") if el else None
        return {"url": absolute(u), "slug": slug_from_url(u)} if u and u != "undefined" else None
    info = soup.select_one(".episode-anime-info .anime-information")
    anime_title = clean(info.select_one("h4")) if info else None
    anime_poster = image_of(info.select_one(".anime-featured img")) if info else None
    anime_metadata = [clean(x) for x in info.select(".anime-metadata span") if clean(x)] if info else []
    synopsis = clean(info.select_one(".anime-synopsis")) if info else None
    score = clean(soup.select_one(".anime-score-counts"))
    return {"id": post_id, "slug": slug_from_url(page_url), "url": page_url,
            "number": current_num, "title": clean(soup.title),
            "anime": {"id": anime_id, "title": anime_title, "url": absolute(anime_link.get("href")) if anime_link else None,
                      "slug": slug_from_url(anime_link.get("href")) if anime_link else None,
                      "poster": anime_poster, "metadata": anime_metadata, "synopsis": synopsis},
            "player": {"type": "iframe", "default_server": next((x["id"] for x in servers if x["default"]), None),
                       "initial_embed_url": absolute(iframe.get("src")) if iframe else None, "servers": servers},
            "navigation": {"previous": nav(prev_el), "next": nav(next_el)},
            "episode_list": episodes,
            "rating": {"display": score, "votes": None},
            "actions": {"can_report": bool(soup.select_one("[data-report-modal]")),
                        "can_add_to_watchlist": bool(watchlist)},
            "seo": {"title": clean(soup.title), "description": (soup.select_one('meta[name="description"]') or {}).get("content"),
                    "canonical_url": (soup.select_one('link[rel="canonical"]') or {}).get("href")}}
