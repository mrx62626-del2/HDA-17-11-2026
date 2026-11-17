import logging
import re
import requests
from app.config import BASE_URL, REQUEST_TIMEOUT, USER_AGENT

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

logger = logging.getLogger("hda.source")

class SourceError(RuntimeError):
    pass

class SourceClient:
    def __init__(self):
        # cloudscraper is retained as a compatible HTTP session implementation.
        # It is not a guarantee of access if the origin blocks automated traffic.
        self.session = cloudscraper.create_scraper() if cloudscraper else requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Referer": BASE_URL + "/",
            "Cache-Control": "no-cache",
        })

    def get_html(self, url_or_path):
        url = url_or_path if url_or_path.startswith(("http://", "https://")) else BASE_URL + "/" + url_or_path.lstrip("/")
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            content_type = response.headers.get("Content-Type", "")
            title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text[:50000], re.I | re.S)
            title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "(no title)"
            logger.info(
                "Source response: status=%s final_url=%s content_type=%s bytes=%s title=%r redirects=%s",
                response.status_code, response.url, content_type, len(response.content), title[:180],
                [r.status_code for r in response.history],
            )
            response.raise_for_status()
            if not response.text.strip():
                raise SourceError("Source returned an empty response")
            if "html" not in content_type.lower():
                raise SourceError(f"Expected HTML from source, received Content-Type: {content_type or 'missing'}")
            return response.text, response.url
        except requests.RequestException as exc:
            logger.exception("Source request failed for %s", url)
            raise SourceError(f"Could not retrieve source page: {exc}") from exc
        except SourceError:
            raise

source = SourceClient()
