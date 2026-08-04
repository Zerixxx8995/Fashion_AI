"""
Meesho Spider — scraper/spiders/meesho_spider.py

Scrapes Meesho.com for fashion products across canonical categories.
Routes requests through ScraperAPI proxy and publishes to Redis Streams.

Product model schema mapping:
  platform:          "meesho"
  platform_id:       Meesho product ID (usually numeric slug at end of URL)
  name:              Product name
  brand:             Brand name (usually blank or seller brand name on Meesho)
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


class MeeshoSpider(scrapy.Spider):
    name = "meesho"
    allowed_domains = ["meesho.com", "www.meesho.com"]
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
            url = f"https://www.meesho.com/search?q={query.replace(' ', '+')}"
            logger.info("[meesho_spider] Starting category: %s → %s", category_key, url)
            yield self._make_request(url, category_key, 1)

    def _make_request(self, url: str, category_key: str, page_num: int):
        return scrapy.Request(
            url=url,
            callback=self.parse_listing,
            errback=self.handle_error,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    # Wait for Meesho product card containers
                    PageMethod("wait_for_selector", "div[class*='ProductList__GridCol']", timeout=20_000),
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
            logger.warning("[meesho_spider] Blocked (%d) on %s", response.status, response.url)
            return

        canonical_category = CATEGORY_CANONICAL.get(category_key, category_key)
        
        # Meesho has product link tags inside grid items.
        # Selectors find links that end in /p/<id> or contain /p/
        product_links = response.css("a[href*='/p/']")

        logger.info(
            "[meesho_spider] Category=%s Page=%d — found %d product links",
            category_key, page_num, len(product_links)
        )

        for link in product_links:
            href = link.attrib.get("href", "").strip()
            if not href:
                continue

            product_url = urljoin("https://www.meesho.com", href)
            
            # Meesho ID is usually the last segment of the url path after /p/
            # e.g. /trendy-kurta/p/8x3a9 → 8x3a9
            platform_id_match = re.search(r"/p/([a-zA-Z0-9]+)$", href)
            platform_id = platform_id_match.group(1) if platform_id_match else href.split("/")[-1]

            # Try to scrape name, price, images relative to the card container
            # Meesho cards typically contain a name paragraph and price heading
            name = link.css("p[class*='ProductTitle']::text").get("") or link.css("span[class*='ProductTitle']::text").get("") or link.css("p::text").get("")
            name = name.strip() if name else ""

            if not name:
                continue

            price_text = link.css("h5::text").get("") or link.css("h4::text").get("") or link.css("p[class*='Price']::text").get("")
            price_inr = self._parse_price(price_text)

            img_url = link.css("img::attr(src)").get("")
            img_urls = [img_url] if img_url else []

            yield {
                "platform": "meesho",
                "platform_id": platform_id,
                "name": name,
                "brand": "",  # Meesho does not traditionally show brands on search lists
                "price_inr": price_inr,
                "stock_image_urls": img_urls,
                "category": canonical_category,
                "url": product_url,
                "seller_id": "",
                "review_image_urls": [],
            }

        # Pagination
        # Note: Meesho search results scroll infinitely or paginate with standard scroll.
        # Since we use PageMethod scrolls, we get a good amount of items per page.
        # If there's an explicit Next button or cursor, we can follow it, but generally
        # search query paging works by appending page/cursor. For Meesho, appending `page`
        # query param is supported: e.g. /search?q=tops&page=2
        if len(product_links) > 0 and page_num < self.max_pages:
            next_page = page_num + 1
            parsed_url = urlparse(response.url)
            qs = parse_qs(parsed_url.query)
            query_val = qs.get("q", [category_key])[0]
            next_url = f"https://www.meesho.com/search?q={query_val.replace(' ', '+')}&page={next_page}"
            logger.info("[meesho_spider] Following page %d: %s", next_page, next_url)
            yield self._make_request(next_url, category_key, next_page)

    @staticmethod
    def _parse_price(text: str):
        if not text:
            return None
        # Remove ₹, commas, and handle "onwards"
        # e.g. "₹299 onwards" → 299
        clean = re.sub(r"[^\d]", "", text)
        return int(clean) if clean else None

    def handle_error(self, failure):
        logger.error("[meesho_spider] Error: %s", failure.request.url)
from urllib.parse import urlparse
