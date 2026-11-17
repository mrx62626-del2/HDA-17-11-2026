import os
from dotenv import load_dotenv
load_dotenv()

BASE_URL = os.getenv("SOURCE_BASE_URL", "https://hindidubanime.com").rstrip("/")
# The supplied WordPress homepage is published at /homepage/, not at /.
HOMEPAGE_PATH = os.getenv("HOMEPAGE_PATH", "/homepage/")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "25"))
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "900"))
DETAILS_CACHE_TTL = int(os.getenv("DETAILS_CACHE_TTL_SECONDS", "1800"))
PLAYER_CACHE_TTL = int(os.getenv("PLAYER_CACHE_TTL_SECONDS", "180"))
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
