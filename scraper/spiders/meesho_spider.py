"""
Meesho Spider — scraper/spiders/meesho_spider.py

Scrapes Meesho.com for fashion products across canonical categories.
Routes requests through ScraperAPI proxy (render=true required — Meesho is
a client-side Next.js app and products are not present in static HTML).
Publishes scraped items to Redis Streams.

Product model schema mapping:
  platform:          "meesho"
  platform_id:       Meesho product ID (alphanumeric slug at end of /p/<id>)
  name:              Product name
  brand:             Brand name (usually blank on Meesho listing pages)
  price_inr:         Current price in INR (parsed to integer)
  stock_image_urls:  List of image URLs
  category:          Canonical category slug
  url:               Full product URL
  seller_id:         Not available on listing page
  review_image_urls: Empty list
"""

import logging
import re
from urllib.parse import urljoin

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


class MeeshoSpider(scrapy.Spider):
    name = "meesho"
    allowed_domains = ["meesho.com", "www.meesho.com"]
    # Meesho is a client-side Next.js app — product cards only exist in JS-rendered HTML
    scraperapi_render = True
    custom_settings = {
        "DOWNLOAD_DELAY": 4,
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
            url = f"https://www.meesho.com/search?q={query.replace(' ', '+')}"
            logger.info("[meesho_spider] Starting category: %s → %s", category_key, url)
            yield self._make_request(url, category_key, 1)

    def _make_request(self, url: str, category_key: str, page_num: int):
        return scrapy.Request(
            url=url,
            callback=self.parse_listing,
            errback=self.handle_error,
            meta={
                "_original_url": url,
                "category_key": category_key,
                "page_num": page_num,
                "handle_httpstatus_list": [403, 404, 410, 429, 503],
            },
        )

    def parse_listing(self, response):
        category_key = response.meta["category_key"]
        page_num = response.meta["page_num"]
        canonical_category = CATEGORY_CANONICAL.get(category_key, category_key)

        if response.status in (403, 410, 429, 503):
            logger.warning(
                "[meesho_spider] Blocked/gone (%d) on %s", response.status, response.url
            )
            return

        # Meesho renders product anchors with href containing /p/<id>.
        # The <a> wraps the entire product card (image + details); ProductCard
        # divs are children of these anchors, not the other way around.
        product_links = response.css("a[href*='/p/']")

        # Deduplicate by platform ID (some links appear multiple times)
        seen_pids = set()
        products = []
        for link in product_links:
            href = link.attrib.get("href", "")
            pid_match = re.search(r"/p/([a-zA-Z0-9]+)", href)
            if not pid_match:
                continue
            pid = pid_match.group(1)
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            products.append((link, pid, href))

        logger.info(
            "[meesho_spider] Category=%s Page=%d — found %d unique product links",
            category_key, page_num, len(products),
        )

        for link, platform_id, href in products:
            all_texts = [t.strip() for t in link.css("::text").getall() if t.strip()]

            # Text order: ['+N More'?], 'Product Name', '₹Price', [rating, reviews...]
            name = ""
            price_inr = None
            for t in all_texts:
                if not name and not t.startswith("+") and not t.startswith("₹") and len(t) > 4:
                    name = t
                if not price_inr and t.startswith("₹"):
                    price_raw = re.sub(r"[^\d]", "", t)
                    price_inr = int(price_raw) if price_raw else None

            if not name:
                continue

            product_url = urljoin("https://www.meesho.com", href)
            img_url = link.css("img::attr(src)").get("") or ""
            img_urls = [img_url] if img_url else []

            yield {
                "platform": "meesho",
                "platform_id": platform_id,
                "name": name,
                "brand": "",  # Meesho does not show brand on search listing pages
                "price_inr": price_inr,
                "stock_image_urls": img_urls,
                "category": canonical_category,
                "url": product_url,
                "seller_id": "",
                "review_image_urls": [],
            }

        # Pagination: Meesho uses ?page=N query param
        if products and page_num < self.max_pages:
            next_page = page_num + 1
            original_url = response.meta.get("_original_url", "")
            # Strip existing page param and append new one
            base = original_url.split("&page=")[0]
            next_url = f"{base}&page={next_page}"
            logger.info("[meesho_spider] Following page %d: %s", next_page, next_url)
            yield self._make_request(next_url, category_key, next_page)

    @staticmethod
    def _parse_price(text: str):
        if not text:
            return None
        clean = re.sub(r"[^\d]", "", text)
        return int(clean) if clean else None

    def handle_error(self, failure):
        logger.error("[meesho_spider] Error: %s", failure.request.url)
