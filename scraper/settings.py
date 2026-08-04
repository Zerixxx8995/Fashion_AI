"""
Scrapy Settings — scraper project.

Full settings for the Fashion AI scraper layer:
  - ScraperAPI rotating proxy middleware
  - Playwright integration for JS-heavy pages (Myntra)
  - Upstash Redis Streams pipeline
  - Conservative crawl rate to avoid bans
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Project identity
# ---------------------------------------------------------------------------
BOT_NAME = "fashion_scraper"
SPIDER_MODULES = ["spiders"]
NEWSPIDER_MODULE = "spiders"

# ---------------------------------------------------------------------------
# Crawl politeness
# ---------------------------------------------------------------------------
ROBOTSTXT_OBEY = False          # ScraperAPI handles robots compliance per TOS
DOWNLOAD_DELAY = 2              # 2s base delay between requests
RANDOMIZE_DOWNLOAD_DELAY = True # 0.5x – 1.5x of DOWNLOAD_DELAY
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 15
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# ---------------------------------------------------------------------------
# Downloader middlewares
# Priority order: lower number = executed first on request,
#                              = executed last on response
# ---------------------------------------------------------------------------
DOWNLOADER_MIDDLEWARES = {
    # Disable Scrapy's default UserAgent middleware
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    # Disable Scrapy's default RetryMiddleware (will keep our own)
    # "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
    # ScraperAPI proxy + credit monitor (must run BEFORE HttpCompressionMiddleware)
    "middlewares.proxy_middleware.ScraperAPIProxyMiddleware": 350,
    # Playwright downloader (renders JS before Scrapy parses)
    "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler": None,
}

# ---------------------------------------------------------------------------
# Playwright downloader handlers
# ---------------------------------------------------------------------------
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ],
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30_000  # 30s

# ---------------------------------------------------------------------------
# Item pipelines
# Priority: lower number = runs first
# ---------------------------------------------------------------------------
ITEM_PIPELINES = {
    "pipelines.redis_streams_pipeline.RedisStreamsPipeline": 100,
}

# ---------------------------------------------------------------------------
# External service credentials (loaded from .env)
# ---------------------------------------------------------------------------
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")
SCRAPERAPI_CREDIT_WARNING_THRESHOLD = 500   # warn if remaining credits < 500

UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

# Redis stream name — must match what the ml-backend consumer listens to
REDIS_SCRAPED_PRODUCTS_STREAM = "scraped:products"
REDIS_STREAM_MAX_LEN = 50_000   # trim stream to latest 50k entries

# ---------------------------------------------------------------------------
# Output / feeds (disabled — we use the Redis Streams pipeline)
# ---------------------------------------------------------------------------
FEEDS = {}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"

# ---------------------------------------------------------------------------
# Twisted asyncio reactor (required for scrapy-playwright)
# ---------------------------------------------------------------------------
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
