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

    def process_request(self, request: Request, spider):
        """
        Attach ScraperAPI proxy credentials to every outbound request.
        ScraperAPI supports two integration modes:
          1. HTTP proxy with CONNECT — set meta['proxy']
          2. URL-rewrite API endpoint — wrap url in scraperapi.com endpoint

        We use mode 1 (HTTP CONNECT proxy) as it works cleanly with Playwright.
        """
        if request.meta.get("_scraperapi_routed"):
            # Already routed — skip to avoid infinite loop
            return

        proxy_url = (
            f"http://scraperapi.render=true.country_code=in:{self.api_key}"
            f"@{self.PROXY_HOST}:{self.PROXY_PORT}"
        )

        request.meta["proxy"] = proxy_url
        request.meta["_scraperapi_routed"] = True

        logger.debug(
            "[proxy_middleware] Routing %s → ScraperAPI proxy (render=true, IN)",
            request.url,
        )

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
