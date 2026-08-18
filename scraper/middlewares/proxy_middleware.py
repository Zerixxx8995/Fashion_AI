"""
ScraperAPI Proxy Middleware — scraper/middlewares/proxy_middleware.py

Responsibility:
  1. Route every outbound Scrapy request through ScraperAPI's rotating proxy
     endpoint so Myntra's anti-bot systems see legitimate residential IPs.
  2. Read the `x-sapi-remaining-credits` response header and log a WARNING
     when remaining credits fall below the configured threshold.

ScraperAPI proxy URL format:
    http://scraperapi:<API_KEY>@proxy-server.scraperapi.com:8001

ScraperAPI-specific query params (appended to the target URL):
    - render=true   → wait for JavaScript to execute (required for Myntra)
    - country_code=in → prefer Indian residential proxies

Credit monitoring:
    The `x-sapi-remaining-credits` header is returned on every response.
    We check it in process_response() and emit a WARNING if below threshold.
"""

import logging

from scrapy import signals
from scrapy.exceptions import NotConfigured
from scrapy.http import Request

logger = logging.getLogger(__name__)


class ScraperAPIProxyMiddleware:
    """
    Downloader middleware that:
      - Rewrites requests to route through ScraperAPI rotating proxy
      - Monitors x-sapi-remaining-credits and warns when running low
    """

    PROXY_HOST = "proxy-server.scraperapi.com"
    PROXY_PORT = 8001

    def __init__(self, api_key: str, credit_threshold: int):
        if not api_key:
            raise NotConfigured("SCRAPERAPI_KEY is not set — ScraperAPI middleware disabled")
        self.api_key = api_key
        self.credit_threshold = credit_threshold
        logger.info(
            "[proxy_middleware] ScraperAPIProxyMiddleware enabled "
            "(credit warning threshold: %d)",
            credit_threshold,
        )

    # -------------------------------------------------------------------------
    # Scrapy factory — reads from spider settings
    # -------------------------------------------------------------------------

    @classmethod
    def from_crawler(cls, crawler):
        api_key = crawler.settings.get("SCRAPERAPI_KEY", "")
        threshold = crawler.settings.getint("SCRAPERAPI_CREDIT_WARNING_THRESHOLD", 500)
        obj = cls(api_key=api_key, credit_threshold=threshold)
        crawler.signals.connect(obj.spider_opened, signal=signals.spider_opened)
        return obj

    def spider_opened(self, spider):
        logger.info("[proxy_middleware] Spider opened: %s", spider.name)

    # -------------------------------------------------------------------------
    # Request processing — route through ScraperAPI
    # -------------------------------------------------------------------------

    SCRAPERAPI_ENDPOINT = "https://api.scraperapi.com/"

    def process_request(self, request: Request, spider):
        """
        Route requests through ScraperAPI using URL-rewrite mode (mode 2).

        ScraperAPI URL-rewrite mode:
          Wraps the target URL as a query param to ScraperAPI's endpoint.
          ScraperAPI renders the page in their cloud (render=true) and returns
          the fully-rendered HTML as a plain HTTP response.

          This avoids the need for a local Playwright browser entirely, which
          means no scrapy-playwright / ProactorEventLoop issues on Windows.

          In production (Linux Docker), we can switch to proxy CONNECT mode
          by setting SCRAPERAPI_MODE=proxy in the environment.
        """
        if request.meta.get("_scraperapi_routed"):
            # Already routed — skip to avoid infinite loop
            return

        from urllib.parse import urlencode
        params = {
            "api_key": self.api_key,
            "url": request.url,
            "render": "true",
            "country_code": "in",
        }
        api_url = self.SCRAPERAPI_ENDPOINT + "?" + urlencode(params)

        new_request = request.replace(
            url=api_url,
            meta={**request.meta, "_scraperapi_routed": True, "playwright": False},
        )

        logger.debug(
            "[proxy_middleware] Routing %s → ScraperAPI URL-rewrite (render=true, IN)",
            request.url,
        )
        return new_request

    # -------------------------------------------------------------------------
    # Response processing — credit monitoring
    # -------------------------------------------------------------------------

    def process_response(self, request: Request, response, spider):
        """
        Read x-sapi-remaining-credits from the response header.
        Emit a WARNING log if remaining credits fall below the configured threshold.
        This is the Step 10 credit monitoring hook referenced in the project plan.
        """
        raw_credits = response.headers.get("x-sapi-remaining-credits", None)
        if raw_credits is not None:
            try:
                remaining = int(raw_credits.decode("utf-8"))
                if remaining < self.credit_threshold:
                    logger.warning(
                        "[proxy_middleware] ⚠️  ScraperAPI credits LOW: %d remaining "
                        "(threshold: %d). Top up at https://www.scraperapi.com/",
                        remaining,
                        self.credit_threshold,
                    )
                else:
                    logger.debug(
                        "[proxy_middleware] ScraperAPI credits OK: %d remaining",
                        remaining,
                    )
            except (ValueError, AttributeError):
                logger.debug(
                    "[proxy_middleware] Could not parse x-sapi-remaining-credits header"
                )

        return response

    def process_exception(self, request: Request, exception, spider):
        logger.error(
            "[proxy_middleware] Request failed via ScraperAPI proxy: %s — %s",
            request.url,
            exception,
        )
        # Return None to let Scrapy's retry middleware handle it
        return None
