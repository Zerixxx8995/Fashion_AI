"""
Myntra Spider — scraper/spiders/myntra_spider.py

Scrapes Myntra for trending and bestseller fashion products across
hardcoded Indian fashion categories.

Architecture:
  - Uses scrapy-playwright to render JavaScript (Myntra is a React SPA)
  - ScraperAPI proxy middleware routes all requests through rotating IPs
  - Items are published to Redis Streams via redis_streams_pipeline

Scraped data per item (matches Product model schema):
  platform:          "myntra"
  platform_id:       Myntra product ID (from URL or data attribute)
  name:              Product display name
  brand:             Brand name
  price_inr:         Discounted / current price in INR (integer)
  stock_image_urls:  List of stock image URLs from the listing page
  category:          Canonical category slug
  url:               Full Myntra product URL
  seller_id:         Not available on listing pages — left blank
  review_image_urls: Empty list on listing pages (populated by review scrape job)

Scraping strategy:
  1. Start from Myntra category listing pages (search results / trending)
  2. Playwright renders the SPA and waits for product cards to appear
  3. We extract product metadata from the listing page (no need to visit each PDP)
  4. Pagination: follow "load more" or page numbers up to MAX_PAGES

Anti-ban notes:
  - ScraperAPI handles IP rotation and browser fingerprint spoofing
  - render=true is enabled in the proxy middleware for JS rendering
  - DOWNLOAD_DELAY + RANDOMIZE_DOWNLOAD_DELAY add natural pacing
  - User-Agent is managed by ScraperAPI
"""

import json
import logging
import re
from urllib.parse import urlencode, urljoin

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Myntra category → canonical slug mapping
# ---------------------------------------------------------------------------
# Myntra URL fragments for category listing pages
CATEGORY_URLS = {
    "tops": "https://www.myntra.com/tops",
    "tshirts": "https://www.myntra.com/tshirts",
    "kurtas": "https://www.myntra.com/kurtas",
    "dresses": "https://www.myntra.com/dresses",
    "jeans": "https://www.myntra.com/jeans",
    "sarees": "https://www.myntra.com/sarees",
    "sneakers": "https://www.myntra.com/sports-shoes",
    "footwear": "https://www.myntra.com/casual-shoes",
    "accessories": "https://www.myntra.com/accessories",
    "bottomwear": "https://www.myntra.com/trousers",
}

# Canonical category labels (matches Product model)
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

MAX_PAGES = 3           # How many listing pages per category to scrape
PRODUCTS_PER_PAGE = 40  # Myntra shows 40 products per page


class MyntraSpider(scrapy.Spider):
    name = "myntra"
    allowed_domains = [
        "www.myntra.com", "myntra.com",
        # Required for ScraperAPI URL-rewrite mode (Windows dev).
        # ScraperAPI rewrites target URLs through api.scraperapi.com.
        "api.scraperapi.com",
    ]
    custom_settings = {
        # Override global settings for Myntra-specific tuning
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, categories=None, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow CLI override: scrapy crawl myntra -a categories=tops,jeans
        if categories:
            cat_list = [c.strip() for c in categories.split(",")]
            self.start_categories = {k: v for k, v in CATEGORY_URLS.items() if k in cat_list}
        else:
            self.start_categories = CATEGORY_URLS

        self.max_pages = int(max_pages) if max_pages else MAX_PAGES
        logger.info(
            "[myntra_spider] Configured to scrape %d categories, up to %d pages each",
            len(self.start_categories),
            self.max_pages,
        )

    # -------------------------------------------------------------------------
    # Start requests — one per category
    # -------------------------------------------------------------------------

    async def start(self):
        """
        Scrapy 2.13+ async entry point. Delegates to start_requests() so
        requests are dispatched properly by the async engine.
        """
        for request in self.start_requests():
            yield request

    def start_requests(self):
        for category_key, base_url in self.start_categories.items():
            logger.info("[myntra_spider] Starting category: %s → %s", category_key, base_url)
            yield self._make_listing_request(
                url=base_url,
                category_key=category_key,
                page_num=1,
            )

    def _make_listing_request(self, url: str, category_key: str, page_num: int):
        """
        Build a Scrapy request for a Myntra listing page.
        Uses Playwright to render the SPA and waits for product cards.
        """
        # Myntra paginates via `p` query param
        if page_num > 1:
            url = f"{url}?p={page_num}"

        return scrapy.Request(
            url=url,
            callback=self.parse_listing,
            errback=self.handle_error,
            meta={
                # Store original Myntra URL so pagination can reconstruct it
                # even after ScraperAPI URL-rewrite changes response.url.
                "_original_url": url,
                "category_key": category_key,
                "page_num": page_num,
                "handle_httpstatus_list": [403, 404, 429, 503],
            },
        )

    # -------------------------------------------------------------------------
    # Parse listing page
    # -------------------------------------------------------------------------

    async def parse_listing(self, response):
        page = response.meta.get("playwright_page")
        category_key = response.meta["category_key"]
        page_num = response.meta["page_num"]

        if page:
            await page.close()

        # Check for block / CAPTCHA
        if response.status in (403, 429, 503):
            logger.warning(
                "[myntra_spider] Received %d on %s — ScraperAPI may need render=true upgrade",
                response.status,
                response.url,
            )
            return

        canonical_category = CATEGORY_CANONICAL.get(category_key, category_key)

        # --- Extract product cards from the listing ---
        # Myntra renders product cards in <li class="product-base"> elements
        product_cards = response.css("li.product-base")

        if not product_cards:
            # Fall back to JSON-LD / window.__myst_initial_state__ embedded data
            for fallback_item in self._extract_from_js_state(response, canonical_category):
                yield fallback_item
            return

        logger.info(
            "[myntra_spider] Category=%s Page=%d — found %d product cards",
            category_key,
            page_num,
            len(product_cards),
        )

        for card in product_cards:
            item = self._parse_product_card(card, canonical_category)
            if item:
                yield item

        # --- Pagination ---
        if len(product_cards) >= PRODUCTS_PER_PAGE and page_num < self.max_pages:
            next_page = page_num + 1
            # Use the original Myntra URL stored in meta — response.url now points
            # to api.scraperapi.com after URL-rewrite, not the original Myntra URL.
            original_url = response.meta.get("_original_url", "").split("?")[0]
            if not original_url:
                # Fallback: reconstruct from start_categories
                original_url = self.start_categories.get(category_key, "")
            logger.info(
                "[myntra_spider] Following page %d for category=%s → %s",
                next_page,
                category_key,
                original_url,
            )
            yield self._make_listing_request(
                url=original_url,
                category_key=category_key,
                page_num=next_page,
            )

    # -------------------------------------------------------------------------
    # Card parser — extracts from rendered HTML product cards
    # -------------------------------------------------------------------------

    def _parse_product_card(self, card, canonical_category: str):
        """
        Extract product data from a single <li class="product-base"> card.
        Returns a dict matching the Product schema, or None if data is incomplete.
        """
        # Product URL + platform_id
        # Try multiple selector patterns — Myntra's HTML structure varies
        relative_url = (
            card.css("a.product-base::attr(href)").get("")
            or card.css("a[href*='/buy']::attr(href)").get("")
            or card.css("a[href]::attr(href)").get("")
        ).strip()
        if not relative_url:
            logger.debug("[myntra_spider] Card has no href. HTML snippet: %s", card.get()[:300])
            return None

        product_url = urljoin("https://www.myntra.com", relative_url)
        # Myntra product ID is the numeric segment at the end of the URL path
        # e.g., /h-and-m/tshirt/28845766/buy → 28845766
        platform_id_match = re.search(r"/(\d+)/buy", relative_url)
        if not platform_id_match:
            platform_id_match = re.search(r"/(\d+)$", relative_url.rstrip("/"))
        platform_id = platform_id_match.group(1) if platform_id_match else relative_url

        # Name
        brand = card.css(".product-brand::text").get("").strip()
        product_name = card.css(".product-product::text").get("").strip()
        full_name = f"{brand} {product_name}".strip() if brand else product_name

        if not full_name:
            return None

        # Price — try multiple selector patterns for Myntra's various layouts
        price_text = (
            card.css(".product-discountedPrice::text").get("")
            or card.css(".product-price span::text").get("")
            or card.css("[class*='discountedPrice']::text").get("")
            or card.css("[class*='Price']::text").get("")
            or card.css(".product-price::text").get("")
            or ""
        )
        price_inr = self._parse_price(price_text)

        # Stock image URLs — Myntra loads images lazily; data-src is the URL
        img_urls = []
        for img in card.css("img.img-responsive"):
            src = img.attrib.get("data-src") or img.attrib.get("src") or ""
            if src and src.startswith("http"):
                img_urls.append(src)

        return {
            "platform": "myntra",
            "platform_id": platform_id,
            "name": full_name,
            "brand": brand,
            "price_inr": price_inr,
            "stock_image_urls": img_urls,
            "category": canonical_category,
            "url": product_url,
            "seller_id": "",          # Not available on listing pages
            "review_image_urls": [],  # Scraped by a separate review job
        }

    # -------------------------------------------------------------------------
    # JS state extractor — fallback when Playwright CSS selectors miss
    # -------------------------------------------------------------------------

    def _extract_from_js_state(self, response, canonical_category: str):
        """
        Myntra embeds product data in window.__myst_initial_state__ as a JSON blob.
        This is a reliable fallback when the CSS selectors don't match.
        """
        # Find the JSON blob in the page source
        pattern = r"window\.__myst_initial_state__\s*=\s*(\{.+?\});?\s*</script>"
        match = re.search(pattern, response.text, re.DOTALL)
        if not match:
            logger.warning(
                "[myntra_spider] No product cards and no JS state found on %s",
                response.url,
            )
            return

        try:
            state = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logger.warning(
                "[myntra_spider] Failed to parse JS state JSON on %s: %s",
                response.url,
                exc,
            )
            return

        # Navigate the nested state structure to find product listings
        # Myntra's state shape varies; we search for a list with productId fields
        products = self._find_products_in_state(state)
        logger.info(
            "[myntra_spider] JS state fallback — found %d products on %s",
            len(products),
            response.url,
        )

        for p in products:
            platform_id = str(p.get("productId") or p.get("id") or "")
            if not platform_id:
                continue

            name = p.get("productName") or p.get("name") or ""
            brand = p.get("brandName") or p.get("brand") or ""
            full_name = f"{brand} {name}".strip() if brand else name
            if not full_name:
                continue

            price_inr = None
            pricing = p.get("priceInfo") or p.get("price") or {}
            if isinstance(pricing, dict):
                price_inr = pricing.get("discounted") or pricing.get("mrp")
            elif isinstance(pricing, (int, float)):
                price_inr = int(pricing)

            images = p.get("images") or []
            img_urls = []
            for img in images:
                if isinstance(img, dict):
                    src = img.get("src") or img.get("url") or ""
                elif isinstance(img, str):
                    src = img
                else:
                    src = ""
                if src and src.startswith("http"):
                    img_urls.append(src)

            slug = p.get("landingPageUrl") or p.get("slug") or f"/{platform_id}/buy"
            product_url = urljoin("https://www.myntra.com", slug)

            yield {
                "platform": "myntra",
                "platform_id": platform_id,
                "name": full_name,
                "brand": brand,
                "price_inr": int(price_inr) if price_inr else None,
                "stock_image_urls": img_urls,
                "category": canonical_category,
                "url": product_url,
                "seller_id": "",
                "review_image_urls": [],
            }

    def _find_products_in_state(self, obj, depth=0):
        """
        Recursively search a JSON-decoded dict/list for an array that looks
        like a product list (has productId or name+brandName keys).
        """
        if depth > 8:
            return []

        if isinstance(obj, list):
            # Check if this looks like a product list
            if obj and isinstance(obj[0], dict):
                if "productId" in obj[0] or ("name" in obj[0] and "brandName" in obj[0]):
                    return obj
            # Otherwise recurse
            for item in obj:
                result = self._find_products_in_state(item, depth + 1)
                if result:
                    return result

        elif isinstance(obj, dict):
            for key, value in obj.items():
                result = self._find_products_in_state(value, depth + 1)
                if result:
                    return result

        return []

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_price(text: str):
        """
        Parse a price string like "Rs. 1,299" or "₹1299" → integer 1299.
        Returns None if price cannot be parsed.
        """
        if not text:
            return None
        # Strip currency symbols, commas, whitespace
        clean = re.sub(r"[^\d]", "", text)
        return int(clean) if clean else None

    def handle_error(self, failure):
        logger.error(
            "[myntra_spider] Request failed: %s — %s",
            failure.request.url,
            failure.value,
        )
