"""
Schema and unit tests for the Myntra spider.

Tests that:
  - The spider name and category configuration are correct
  - _parse_price correctly handles various Indian price formats
  - _find_products_in_state correctly locates product arrays in nested state
  - Items produced match the Product model schema fields
  - Required fields (platform, platform_id, name, url) are always present
  - pipeline drops items with missing required fields
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import pytest

# -------------------------------------------------------------------------
# Spider tests
# -------------------------------------------------------------------------

from spiders.myntra_spider import MyntraSpider, CATEGORY_URLS, CATEGORY_CANONICAL

REQUIRED_FIELDS = {"platform", "platform_id", "name", "url"}
PRODUCT_SCHEMA_FIELDS = {
    "platform", "platform_id", "name", "brand",
    "price_inr", "stock_image_urls", "category", "url",
    "seller_id", "review_image_urls",
}


class TestMyntraSpider:

    def test_spider_name(self):
        assert MyntraSpider.name == "myntra"

    def test_default_categories_configured(self):
        assert len(CATEGORY_URLS) == 10
        for cat in ("tops", "tshirts", "kurtas", "dresses", "jeans",
                    "sarees", "sneakers", "footwear", "accessories", "bottomwear"):
            assert cat in CATEGORY_URLS, f"Missing category: {cat}"

    def test_all_category_urls_are_myntra(self):
        for cat, url in CATEGORY_URLS.items():
            assert "myntra.com" in url, f"Non-Myntra URL for category {cat}: {url}"

    def test_category_canonical_mapping_coverage(self):
        for cat in CATEGORY_URLS:
            assert cat in CATEGORY_CANONICAL, f"No canonical mapping for category: {cat}"

    def test_parse_price_inr_format(self):
        assert MyntraSpider._parse_price("Rs. 1,299") == 1299

    def test_parse_price_rupee_symbol(self):
        assert MyntraSpider._parse_price("₹799") == 799

    def test_parse_price_plain_int(self):
        assert MyntraSpider._parse_price("1999") == 1999

    def test_parse_price_empty_returns_none(self):
        assert MyntraSpider._parse_price("") is None

    def test_parse_price_na_returns_none(self):
        assert MyntraSpider._parse_price("N/A") is None

    def test_parse_price_with_comma_thousands(self):
        assert MyntraSpider._parse_price("₹12,499") == 12499

    def test_find_products_in_state_basic(self):
        state = {
            "pageData": {
                "data": {
                    "products": [
                        {"productId": "123", "productName": "T-Shirt", "brandName": "H&M"},
                        {"productId": "456", "productName": "Kurta", "brandName": "Fabindia"},
                    ]
                }
            }
        }
        spider = MyntraSpider.__new__(MyntraSpider)
        found = spider._find_products_in_state(state)
        assert len(found) == 2
        assert found[0]["productId"] == "123"

    def test_find_products_in_state_empty(self):
        spider = MyntraSpider.__new__(MyntraSpider)
        found = spider._find_products_in_state({})
        assert found == []

    def test_find_products_in_state_deeply_nested(self):
        state = {
            "a": {"b": {"c": {"d": [
                {"productId": "789", "productName": "Jeans", "brandName": "Levi's"},
            ]}}}
        }
        spider = MyntraSpider.__new__(MyntraSpider)
        found = spider._find_products_in_state(state)
        assert len(found) == 1
        assert found[0]["productId"] == "789"

    def test_find_products_in_state_name_brand_format(self):
        """Myntra sometimes uses name/brandName without productId."""
        state = {
            "items": [
                {"name": "Ethnic Kurta", "brandName": "Biba", "id": 111},
                {"name": "Floral Dress", "brandName": "AND", "id": 222},
            ]
        }
        spider = MyntraSpider.__new__(MyntraSpider)
        found = spider._find_products_in_state(state)
        assert len(found) == 2

    def test_start_requests_generates_category_requests(self):
        """Spider generates one request per category at startup."""
        spider = MyntraSpider.__new__(MyntraSpider)
        spider.start_categories = {"tops": "https://www.myntra.com/tops"}
        spider.max_pages = 1
        requests = list(spider.start_requests())
        assert len(requests) == 1
        assert "myntra.com/tops" in requests[0].url

    def test_category_cli_filter(self):
        """Categories can be limited via -a categories CLI argument."""
        spider = MyntraSpider(categories="tops,jeans")
        assert "tops" in spider.start_categories
        assert "jeans" in spider.start_categories
        assert "kurtas" not in spider.start_categories


# -------------------------------------------------------------------------
# Pipeline tests
# -------------------------------------------------------------------------

from pipelines.redis_streams_pipeline import RedisStreamsPipeline
from scrapy.exceptions import DropItem


class MockRedis:
    """Stub Redis that records xadd calls."""
    def __init__(self):
        self.entries = []

    def xadd(self, stream, message, **kwargs):
        self.entries.append((stream, message))
        return "1-0"


class MockSpider:
    name = "test_spider"


class TestRedisStreamsPipeline:

    def _make_pipeline(self):
        pipeline = RedisStreamsPipeline(
            redis_url="https://fake.upstash.io",
            redis_token="fake_token",
            stream_name="scraped:products",
            max_len=50_000,
        )
        pipeline.redis = MockRedis()
        return pipeline

    def _valid_item(self):
        return {
            "platform": "myntra",
            "platform_id": "12345",
            "name": "H&M Regular T-Shirt",
            "brand": "H&M",
            "price_inr": 799,
            "stock_image_urls": ["https://example.com/img1.jpg"],
            "category": "tops",
            "url": "https://www.myntra.com/tshirts/hm/12345/buy",
            "seller_id": "",
            "review_image_urls": [],
        }

    def test_valid_item_is_published(self):
        pipeline = self._make_pipeline()
        item = self._valid_item()
        result = pipeline.process_item(item, MockSpider())
        assert result == item
        assert len(pipeline.redis.entries) == 1

    def test_published_to_correct_stream(self):
        pipeline = self._make_pipeline()
        pipeline.process_item(self._valid_item(), MockSpider())
        stream_name, _ = pipeline.redis.entries[0]
        assert stream_name == "scraped:products"

    def test_published_message_has_platform(self):
        pipeline = self._make_pipeline()
        pipeline.process_item(self._valid_item(), MockSpider())
        _, message = pipeline.redis.entries[0]
        assert message["platform"] == "myntra"

    def test_published_message_has_url(self):
        pipeline = self._make_pipeline()
        pipeline.process_item(self._valid_item(), MockSpider())
        _, message = pipeline.redis.entries[0]
        assert "myntra.com" in message["url"]

    def test_published_stock_image_urls_is_json_string(self):
        pipeline = self._make_pipeline()
        pipeline.process_item(self._valid_item(), MockSpider())
        _, message = pipeline.redis.entries[0]
        parsed = json.loads(message["stock_image_urls"])
        assert isinstance(parsed, list)

    def test_published_review_image_urls_is_json_string(self):
        pipeline = self._make_pipeline()
        pipeline.process_item(self._valid_item(), MockSpider())
        _, message = pipeline.redis.entries[0]
        parsed = json.loads(message["review_image_urls"])
        assert isinstance(parsed, list)

    def test_item_missing_platform_is_dropped(self):
        pipeline = self._make_pipeline()
        item = self._valid_item()
        del item["platform"]
        with pytest.raises(DropItem):
            pipeline.process_item(item, MockSpider())

    def test_item_missing_platform_id_is_dropped(self):
        pipeline = self._make_pipeline()
        item = self._valid_item()
        del item["platform_id"]
        with pytest.raises(DropItem):
            pipeline.process_item(item, MockSpider())

    def test_item_missing_name_is_dropped(self):
        pipeline = self._make_pipeline()
        item = self._valid_item()
        del item["name"]
        with pytest.raises(DropItem):
            pipeline.process_item(item, MockSpider())

    def test_item_missing_url_is_dropped(self):
        pipeline = self._make_pipeline()
        item = self._valid_item()
        del item["url"]
        with pytest.raises(DropItem):
            pipeline.process_item(item, MockSpider())

    def test_drop_count_incremented(self):
        pipeline = self._make_pipeline()
        item = self._valid_item()
        del item["url"]
        with pytest.raises(DropItem):
            pipeline.process_item(item, MockSpider())
        assert pipeline._dropped == 1

    def test_publish_count_incremented(self):
        pipeline = self._make_pipeline()
        pipeline.process_item(self._valid_item(), MockSpider())
        assert pipeline._published == 1

    def test_item_schema_matches_product_model(self):
        """Verify all Product model fields are represented in the pipeline message."""
        pipeline = self._make_pipeline()
        pipeline.process_item(self._valid_item(), MockSpider())
        _, message = pipeline.redis.entries[0]
        expected_keys = {
            "platform", "platform_id", "name", "brand",
            "price_inr", "stock_image_urls", "category",
            "url", "seller_id", "scraped_at", "review_image_urls",
        }
        assert expected_keys == set(message.keys())
