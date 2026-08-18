"""
Flipkart Spider — scraper/spiders/flipkart_spider.py

Scrapes Flipkart.com for fashion products across canonical categories.
Routes requests through ScraperAPI proxy and publishes to Redis Streams.

Product model schema mapping:
  platform:          "flipkart"
  platform_id:       Flipkart Product ID (PID)
  name:              Product name
  brand:             Brand name (extracted from dedicated brand class)
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
from urllib.parse import parse_qs, urljoin, urlparse

import scrapy

logger = logging.getLogger(__name__)

CATEGORY_QUERIES = {
    "tops": "tops for women",
    "tshirts": "tshirts for men",
    "kurtas": "kurta for men",
    "dresses": "dresses for women",
    "jeans": "jeans for men",
    "sarees": "saree",
    "sneakers": "sneakers for men",
    "footwear": "shoes",
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


class FlipkartSpider(scrapy.Spider):
    name = "flipkart"
    allowed_domains = ["flipkart.com", "www.flipkart.com"]
    scraperapi_render = False  # Flipkart static HTML contains product cards
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
            url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
            logger.info("[flipkart_spider] Starting category: %s → %s", category_key, url)
            yield self._make_request(url, category_key, 1)

    def _make_request(self, url: str, category_key: str, page_num: int):
        return scrapy.Request(
            url=url,
            callback=self.parse_listing,
            errback=self.handle_error,
            meta={
                # Store original Flipkart URL so pagination can reconstruct it
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
            logger.warning("[flipkart_spider] Blocked (%d) on %s", response.status, response.url)
            return

        canonical_category = CATEGORY_CANONICAL.get(category_key, category_key)
        
        # Flipkart product cards are usually divs with data-id attribute (which holds the platform product ID / pid)
        cards = response.css("div[data-id]")

        logger.info(
            "[flipkart_spider] Category=%s Page=%d — found %d product cards",
            category_key, page_num, len(cards)
        )

        for card in cards:
            pid = card.attrib.get("data-id", "").strip()
            if not pid or len(pid) < 5:
                continue

            # Flipkart's CSS class names are obfuscated and change frequently.
            # Instead, use the ordered text nodes from the card:
            #   index 0 → brand name
            #   index 1 → product title
            #   index 2 → offer price (e.g. "₹217")
            #   index 4 → original / MRP price (e.g. "799")
            all_texts = [t.strip() for t in card.css("::text").getall() if t.strip()]

            brand = all_texts[0] if len(all_texts) > 0 else ""
            title = all_texts[1] if len(all_texts) > 1 else ""
            full_name = f"{brand} {title}".strip() if brand else title
            if not full_name:
                continue

            # Price: text at index 2 looks like "₹217" — strip non-digit chars
            price_inr = None
            if len(all_texts) > 2:
                price_raw = re.sub(r"[^\d]", "", all_texts[2])
                price_inr = int(price_raw) if price_raw else None

            # Image url — stable tag-based selector
            img_url = card.css("img::attr(src)").get("")
            img_urls = [img_url] if img_url else []

            # URL — first anchor href in the card
            relative_url = card.css("a::attr(href)").get("")
            product_url = urljoin("https://www.flipkart.com", relative_url) if relative_url else ""

            # Standardise Flipkart URL (strip tracking params but retain pid)
            if product_url:
                parsed_url = urlparse(product_url)
                qs = parse_qs(parsed_url.query)
                query_str = f"?pid={qs['pid'][0]}" if "pid" in qs else ""
                product_url = f"https://www.flipkart.com{parsed_url.path}{query_str}"

            yield {
                "platform": "flipkart",
                "platform_id": pid,
                "name": full_name,
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
            # Look for the pagination Next button (usually has text containing 'Next' or span containing 'Next')
            next_url = response.xpath("//a[contains(., 'Next') or span[contains(., 'Next')]]/@href").get()
            if next_url:
                # Use original URL domain since response.url has ScraperAPI domain
                original_url = response.meta.get("_original_url", "")
                base_domain = "https://www.flipkart.com"
                full_next_url = urljoin(base_domain, next_url)
                logger.info("[flipkart_spider] Following page %d: %s", page_num + 1, full_next_url)
                yield self._make_request(full_next_url, category_key, page_num + 1)

    @staticmethod
    def _parse_price(text: str):
        if not text:
            return None
        # Remove ₹, commas, and other non-digits
        clean = re.sub(r"[^\d]", "", text)
        return int(clean) if clean else None

    def handle_error(self, failure):
        logger.error("[flipkart_spider] Error: %s", failure.request.url)
