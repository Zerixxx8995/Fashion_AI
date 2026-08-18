"""
AJIO Spider — scraper/spiders/ajio_spider.py

Scrapes AJIO.com for fashion products across canonical categories.
Routes requests through ScraperAPI proxy and publishes to Redis Streams.

Product model schema mapping:
  platform:          "ajio"
  platform_id:       AJIO product code (extracted from item)
  name:              Product name
  brand:             Brand name
  price_inr:         Current price in INR (parsed to integer)
  stock_image_urls:  List of image URLs
  category:          Canonical category slug
  url:               Full product URL
  seller_id:         Not available on listing page
  review_image_urls: Empty list
"""

import json
import logging
import re
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

# AJIO search endpoints
CATEGORY_QUERIES = {
    "tops": "tops for women",
    "tshirts": "tshirts for men",
    "kurtas": "kurta for men",
    "dresses": "dresses for women",
    "jeans": "jeans for men",
    "sarees": "sarees",
    "sneakers": "sneakers for men",
    "footwear": "shoes for men",
    "accessories": "sunglasses",
    "bottomwear": "trousers for men",
}

CATEGORY_CANONICAL = {
    "tops": "tops",
    "tshirts": "tops",
    "kurtas": "ethnic",
    "dresses": "dresses",
    "jeans": "bottomwear",
    "sarees": "ethnic",
    "sneakers": "footwear",
    "footwear": "footwear",
    "accessories": "accessories",
    "bottomwear": "bottomwear",
}

MAX_PAGES = 3


class AjioSpider(scrapy.Spider):
    name = "ajio"
    allowed_domains = ["ajio.com", "www.ajio.com"]
    scraperapi_render = False
    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, categories=None, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if categories:
            cat_list = [c.strip() for c in categories.split(",")]
            self.queries = {k: v for k, v in CATEGORY_QUERIES.items() if k in cat_list}
        else:
            self.queries = CATEGORY_QUERIES
        self.max_pages = int(max_pages) if max_pages else MAX_PAGES

    async def start(self):
        """
        Scrapy 2.13+ async entry point. Delegates to start_requests() so
        requests are dispatched properly by the async engine.
        """
        for request in self.start_requests():
            yield request

    def start_requests(self):
        for category_key, query in self.queries.items():
            url = f"https://www.ajio.com/search/?text={query.replace(' ', '%20')}"
            logger.info("[ajio_spider] Starting category: %s → %s", category_key, url)
            yield self._make_request(url, category_key, 0) # AJIO pages start at 0

    def _make_request(self, url: str, category_key: str, page_num: int):
        # AJIO handles pagination in search query string via `currentPage` param
        if page_num > 0:
            if "?" in url:
                paginated_url = f"{url}&currentPage={page_num}"
            else:
                paginated_url = f"{url}?currentPage={page_num}"
        else:
            paginated_url = url

        return scrapy.Request(
            url=paginated_url,
            callback=self.parse_listing,
            errback=self.handle_error,
            meta={
                # Store original AJIO URL so pagination can reconstruct it
                "_original_url": paginated_url,
                "category_key": category_key,
                "page_num": page_num,
                "handle_httpstatus_list": [403, 404, 429, 503],
            },
        )

    async def parse_listing(self, response):
        page = response.meta.get("playwright_page")
        category_key = response.meta["category_key"]
        page_num = response.meta["page_num"]

        if page:
            await page.close()

        if response.status in (403, 429, 503):
            logger.warning("[ajio_spider] Blocked (%d) on %s", response.status, response.url)
            return

        canonical_category = CATEGORY_CANONICAL.get(category_key, category_key)

        for item in self._extract_from_preloaded_state(response, canonical_category):
            yield item

        # Fallback to HTML CSS card selectors if preloaded state parsing fails
        cards = response.css("div.item")
        logger.info(
            "[ajio_spider] Category=%s Page=%d — found %d product cards in HTML",
            category_key, page_num, len(cards)
        )

        # Trigger pagination if we got items
        if len(cards) > 0 and page_num < self.max_pages - 1:
            next_page = page_num + 1
            original_url = response.meta.get("_original_url", "")
            base_url = original_url.split("&currentPage=")[0].split("?currentPage=")[0]
            logger.info("[ajio_spider] Following page %d: %s", next_page, base_url)
            yield self._make_request(base_url, category_key, next_page)

    def _extract_from_preloaded_state(self, response, canonical_category: str):
        """
        Extract AJIO search items from __PRELOADED_STATE__ embedded in the page HTML.

        AJIO embeds a large Redux state object in the raw HTML page via:
            __PRELOADED_STATE__ = { ... }
        The state is NOT wrapped in a <script> tag with a clean closing, so we
        use character-level brace matching to extract the full JSON blob.

        Product data is stored at: state["grid"]["entities"] — a dict keyed by
        product code (e.g. "443347797001") with full product metadata.
        """
        MARKER = "__PRELOADED_STATE__ = "
        raw_text = response.text
        idx = raw_text.find(MARKER)
        if idx < 0:
            logger.debug("[ajio_spider] __PRELOADED_STATE__ marker not found in response")
            return

        raw = raw_text[idx + len(MARKER):]

        # Robust brace-match extraction (handles embedded JS without clean </script> boundary)
        depth = 0; end = 0; in_str = False; esc = False
        for i, c in enumerate(raw):
            if esc:
                esc = False
                continue
            if c == '\\' and in_str:
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            if depth == 0 and i > 0:
                end = i + 1
                break

        if not end:
            logger.debug("[ajio_spider] Failed to find end of __PRELOADED_STATE__ blob")
            return

        try:
            state = json.loads(raw[:end])
        except Exception as exc:
            logger.debug("[ajio_spider] JSON parse failed: %s", exc)
            return

        # Product data keyed by product code under state["grid"]["entities"]
        entities: dict = state.get("grid", {}).get("entities", {})
        if not entities:
            logger.debug("[ajio_spider] state[grid][entities] is empty")
            return

        logger.info("[ajio_spider] Extracted %d product entities from state", len(entities))

        for code, item in entities.items():
            if not isinstance(item, dict):
                continue

            platform_id = str(item.get("code") or code)

            # Brand: stored inside fnlColorVariantData.brandName
            variant_data = item.get("fnlColorVariantData") or {}
            brand = (
                variant_data.get("brandName")
                or item.get("brandName")
                or ""
            )

            name = item.get("name") or ""
            full_name = f"{brand} {name}".strip() if brand else name
            if not full_name:
                continue

            # Price: use offerPrice (discounted) if available, fallback to price
            offer_price = item.get("offerPrice") or {}
            base_price = item.get("price") or {}
            price_val = (
                offer_price.get("value")
                or base_price.get("value")
            )

            # Images
            images = item.get("images") or []
            img_urls = []
            for img in images:
                if isinstance(img, dict):
                    img_url = img.get("url", "")
                    if img_url and img_url.startswith("http"):
                        img_urls.append(img_url)

            # URL
            url_slug = item.get("url") or f"/p/{platform_id}"
            product_url = urljoin("https://www.ajio.com", url_slug)

            yield {
                "platform": "ajio",
                "platform_id": platform_id,
                "name": full_name,
                "brand": brand,
                "price_inr": int(price_val) if price_val else None,
                "stock_image_urls": img_urls,
                "category": canonical_category,
                "url": product_url,
                "seller_id": "",
                "review_image_urls": [],
            }


    def handle_error(self, failure):
        logger.error("[ajio_spider] Error: %s", failure.request.url)
