"""
Amazon India Spider — scraper/spiders/amazon_spider.py

Scrapes Amazon.in for fashion products across canonical categories.
Routes requests through ScraperAPI proxy and publishes to Redis Streams.

Product model schema mapping:
  platform:          "amazon"
  platform_id:       ASIN (extracted from data-asin or URL)
  name:              Product title
  brand:             Brand name (extracted from title prefix or merchant node)
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

# Search queries per category
CATEGORY_QUERIES = {
    "tops": "tops for women",
    "tshirts": "tshirts for men",
    "kurtas": "kurta pyjama set",
    "dresses": "dresses for women",
    "jeans": "jeans for men",
    "sarees": "saree for women",
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


class AmazonSpider(scrapy.Spider):
    name = "amazon"
    allowed_domains = ["amazon.in", "www.amazon.in"]
    scraperapi_render = False  # Amazon static HTML contains product cards
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
            url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
            logger.info("[amazon_spider] Starting category: %s → %s", category_key, url)
            yield self._make_request(url, category_key, 1)

    def _make_request(self, url: str, category_key: str, page_num: int):
        return scrapy.Request(
            url=url,
            callback=self.parse_listing,
            errback=self.handle_error,
            meta={
                # Store original Amazon URL so pagination can reconstruct it
                "_original_url": url,
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
            logger.warning("[amazon_spider] Blocked (%d) on %s", response.status, response.url)
            return

        canonical_category = CATEGORY_CANONICAL.get(category_key, category_key)
        cards = response.css("div[data-component-type='s-search-result']")

        logger.info(
            "[amazon_spider] Category=%s Page=%d — found %d product cards",
            category_key, page_num, len(cards)
        )

        for card in cards:
            asin = card.attrib.get("data-asin", "").strip()
            if not asin:
                continue

            # Title — Amazon India uses h2 span (not h2 a span) in static HTML
            name = (
                card.css("h2 span::text").get("")
                or card.css(".a-size-base-plus.a-color-base.a-text-normal::text").get("")
                or card.css("span.a-text-normal::text").get("")
            ).strip()
            if not name:
                continue

            # Brand heuristic: first word/words of the title before common separators
            brand_match = re.match(r"^([A-Za-z0-9&\-]+(?:\s+[A-Za-z0-9&\-]+)?)\s+", name)
            brand = brand_match.group(1) if brand_match else ""

            # Price — .a-price-whole contains digits + commas (e.g. "1,099")
            price_text = card.css(".a-price-whole::text").get("")
            price_inr = self._parse_price(price_text)

            # Image
            img_url = card.css("img.s-image::attr(src)").get("") or card.css("img::attr(src)").get("")
            img_urls = [img_url] if img_url else []

            # URL — prefer a.a-link-normal (actual product link) over h2 a (may be sponsored /sspa/)
            relative_url = (
                card.css("a.a-link-normal.s-no-outline::attr(href)").get("")
                or card.css("h2 a::attr(href)").get("")
            )
            # Ensure we get the real product URL, not a sponsored redirect
            if relative_url and not relative_url.startswith("/sspa"):
                product_url = urljoin("https://www.amazon.in", relative_url)
            elif asin:
                product_url = f"https://www.amazon.in/dp/{asin}"
            else:
                product_url = ""

            yield {
                "platform": "amazon",
                "platform_id": asin,
                "name": name,
                "brand": brand,
                "price_inr": price_inr,
                "stock_image_urls": img_urls,
                "category": canonical_category,
                "url": product_url,
                "seller_id": "",
                "review_image_urls": [],
            }

        # Pagination
        if len(cards) > 0 and page_num < self.max_pages:
            # Look for the Next Page button link
            next_url = response.css("a.s-pagination-next::attr(href)").get()
            if next_url:
                # Use original URL domain since response.url has ScraperAPI domain
                original_url = response.meta.get("_original_url", "")
                base_domain = "https://www.amazon.in"
                full_next_url = urljoin(base_domain, next_url)
                logger.info("[amazon_spider] Following page %d: %s", page_num + 1, full_next_url)
                yield self._make_request(full_next_url, category_key, page_num + 1)

    @staticmethod
    def _parse_price(text: str):
        if not text:
            return None
        # Strip decimal points or non-digit characters
        clean = re.sub(r"[^\d]", "", text.split(".")[0])
        return int(clean) if clean else None

    def handle_error(self, failure):
        logger.error("[amazon_spider] Error: %s", failure.request.url)
