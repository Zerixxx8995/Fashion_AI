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
from scrapy_playwright.page import PageMethod

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
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "div.item", timeout=20_000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight / 2)"),
                    PageMethod("wait_for_timeout", 1000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 1000),
                ],
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
            base_url = response.url.split("&currentPage=")[0].split("?currentPage=")[0]
            logger.info("[ajio_spider] Following page %d: %s", next_page, base_url)
            yield self._make_request(base_url, category_key, next_page)

    def _extract_from_preloaded_state(self, response, canonical_category: str):
        """
        Extract AJIO search items directly from JSON inside window.__PRELOADED_STATE__.
        """
        pattern = r"window\.__PRELOADED_STATE__\s*=\s*(\{.+?\});?\s*</script>"
        match = re.search(pattern, response.text, re.DOTALL)
        if not match:
            return

        try:
            state = json.loads(match.group(1))
            # Preloaded state stores search results under:
            # state['grid']['entities'] or similar. Let's find it.
            entities = state.get("grid", {}).get("entities", []) or state.get("search", {}).get("entities", [])
            
            # If entities is empty, check if we have a searchResult list
            if not entities:
                search_data = state.get("searchResponse", {}) or state.get("gridResponse", {})
                entities = search_data.get("products", []) or search_data.get("results", [])

            for item in entities:
                platform_id = str(item.get("code") or item.get("id") or "")
                if not platform_id:
                    continue

                name = item.get("name") or item.get("title") or ""
                brand = item.get("fn") or item.get("brandName") or ""
                full_name = f"{brand} {name}".strip() if brand else name
                if not full_name:
                    continue

                # Pricing
                price_val = None
                price_data = item.get("price") or item.get("value")
                if isinstance(price_data, dict):
                    price_val = price_data.get("value") or price_data.get("price")
                elif isinstance(price_data, (int, float)):
                    price_val = price_data
                elif isinstance(item.get("price"), dict):
                    price_val = item["price"].get("value")
                
                # Image
                images = item.get("images") or []
                img_urls = []
                for img in images:
                    url = img.get("url") if isinstance(img, dict) else img
                    if url and url.startswith("http"):
                        img_urls.append(url)
                
                # Product URL
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
        except Exception as exc:
            logger.debug("[ajio_spider] Preloaded state parsing failed: %s", exc)

    def handle_error(self, failure):
        logger.error("[ajio_spider] Error: %s", failure.request.url)
