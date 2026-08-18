"""
Redis Streams Pipeline — scraper/pipelines/redis_streams_pipeline.py

Responsibility:
  Publish every scraped product item to an Upstash Redis Stream so the
  ml-backend Celery workers can consume it in real time.

Stream name: scraped:products (configured in settings.py)

Item schema published to stream (mirrors the Product DB model):
  {
    "platform":          "myntra",
    "platform_id":       "12345678",
    "name":              "H&M Regular Fit T-Shirt",
    "brand":             "H&M",
    "price_inr":         "799",
    "stock_image_urls":  '["https://...jpg", "https://...jpg"]',
    "category":          "tops",
    "url":               "https://www.myntra.com/...",
    "seller_id":         "myntra_official",
    "scraped_at":        "2024-01-01T12:00:00Z",
    "review_image_urls": '["https://...jpg"]'   # optional
  }

Redis Streams XADD format:
  All field values must be strings (Redis protocol requirement).
  Lists (stock_image_urls, review_image_urls) are JSON-serialised strings.

Upstash Redis REST client is used because:
  - Upstash provides a serverless Redis with an HTTP REST API
  - Works without maintaining a persistent TCP connection
  - Free tier handles our scraping volume comfortably
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from itemadapter import ItemAdapter
from scrapy import signals
from scrapy.exceptions import DropItem, NotConfigured

logger = logging.getLogger(__name__)

try:
    from upstash_redis import Redis as UpstashRedis
    UPSTASH_AVAILABLE = True
except ImportError:
    UPSTASH_AVAILABLE = False
    logger.warning(
        "[redis_streams_pipeline] upstash-redis not installed. "
        "Install with: pip install upstash-redis"
    )


class RedisStreamsPipeline:
    """
    Scrapy item pipeline that publishes scraped products to a Redis Stream.

    Open: connect to Upstash Redis
    Process: validate required fields → XADD to stream
    Close: log throughput stats
    """

    def __init__(self, redis_url: str, redis_token: str, stream_name: str, max_len: int):
        if not redis_url or not redis_token:
            raise NotConfigured(
                "UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN not set — "
                "Redis Streams pipeline disabled"
            )
        self.redis_url = redis_url
        self.redis_token = redis_token
        self.stream_name = stream_name
        self.max_len = max_len
        self.redis: Any = None
        self._published = 0
        self._dropped = 0

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls(
            redis_url=crawler.settings.get("UPSTASH_REDIS_REST_URL", ""),
            redis_token=crawler.settings.get("UPSTASH_REDIS_REST_TOKEN", ""),
            stream_name=crawler.settings.get("REDIS_SCRAPED_PRODUCTS_STREAM", "scraped:products"),
            max_len=crawler.settings.getint("REDIS_STREAM_MAX_LEN", 50_000),
        )
        crawler.signals.connect(obj.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(obj.spider_closed, signal=signals.spider_closed)
        return obj

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def spider_opened(self, spider):
        if not UPSTASH_AVAILABLE:
            logger.error("[redis_streams_pipeline] upstash-redis unavailable — cannot publish")
            return
        self.redis = UpstashRedis(
            url=self.redis_url,
            token=self.redis_token,
        )
        logger.info(
            "[redis_streams_pipeline] Connected to Upstash Redis stream '%s'",
            self.stream_name,
        )

    def spider_closed(self, spider, reason):
        logger.info(
            "[redis_streams_pipeline] Spider '%s' closed (%s). "
            "Published: %d items, Dropped: %d items.",
            spider.name,
            reason,
            self._published,
            self._dropped,
        )

    # -------------------------------------------------------------------------
    # Item processing
    # -------------------------------------------------------------------------

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # --- Validate required fields ---
        required = ("platform", "platform_id", "name", "url")
        missing = [f for f in required if not adapter.get(f)]
        if missing:
            self._dropped += 1
            raise DropItem(
                f"[redis_streams_pipeline] Dropping item — missing required fields: {missing}. "
                f"Item URL: {adapter.get('url', 'N/A')}"
            )

        # --- Build the stream message ---
        # All values must be strings for Redis XADD protocol
        stock_urls = adapter.get("stock_image_urls") or []
        review_urls = adapter.get("review_image_urls") or []

        message = {
            "platform":          str(adapter.get("platform", "")),
            "platform_id":       str(adapter.get("platform_id", "")),
            "name":              str(adapter.get("name", "")),
            "brand":             str(adapter.get("brand") or ""),
            "price_inr":         str(adapter.get("price_inr") or ""),
            "stock_image_urls":  json.dumps(stock_urls),
            "category":          str(adapter.get("category") or ""),
            "url":               str(adapter.get("url", "")),
            "seller_id":         str(adapter.get("seller_id") or ""),
            "scraped_at":        datetime.now(timezone.utc).isoformat(),
            "review_image_urls": json.dumps(review_urls),
        }

        # --- Publish to Redis Stream ---
        if self.redis is None:
            logger.warning(
                "[redis_streams_pipeline] Redis not connected — skipping item: %s",
                message["url"],
            )
            return item

        try:
            entry_id = self.redis.xadd(
                self.stream_name,
                "*",           # auto-generate stream entry ID
                message,       # data dict (all string values)
                maxlen=self.max_len,
                approximate_trim=True,
            )
            self._published += 1
            logger.debug(
                "[redis_streams_pipeline] Published item to '%s' (id=%s): %s",
                self.stream_name,
                entry_id,
                message["url"],
            )
        except Exception as exc:
            logger.error(
                "[redis_streams_pipeline] Failed to publish item to Redis stream: %s — %s",
                message["url"],
                exc,
            )
            # Don't drop the item — return it so other pipelines can still process it

        return item
