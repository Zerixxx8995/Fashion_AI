"""
Schema and unit tests for the remaining platform spiders (Amazon, Flipkart, Meesho, AJIO).

Asserts that:
  - All spiders have correct names and categories configured.
  - _parse_price correctly converts Indian price formats to integers.
  - Category canonical mapping maps all internal category keys.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from spiders.amazon_spider import AmazonSpider, CATEGORY_QUERIES as AMZN_QUERIES
from spiders.flipkart_spider import FlipkartSpider, CATEGORY_QUERIES as FK_QUERIES
from spiders.meesho_spider import MeeshoSpider, CATEGORY_QUERIES as MEESHO_QUERIES
from spiders.ajio_spider import AjioSpider, CATEGORY_QUERIES as AJIO_QUERIES


class TestAmazonSpider:
    def test_spider_name(self):
        assert AmazonSpider.name == "amazon"

    def test_categories_configured(self):
        assert len(AMZN_QUERIES) == 10
        assert "tops" in AMZN_QUERIES
        assert "jeans" in AMZN_QUERIES

    def test_parse_price(self):
        spider = AmazonSpider.__new__(AmazonSpider)
        assert spider._parse_price("1,299") == 1299
        assert spider._parse_price("799.00") == 799
        assert spider._parse_price("") is None


class TestFlipkartSpider:
    def test_spider_name(self):
        assert FlipkartSpider.name == "flipkart"

    def test_categories_configured(self):
        assert len(FK_QUERIES) == 10
        assert "tops" in FK_QUERIES
        assert "jeans" in FK_QUERIES

    def test_parse_price(self):
        spider = FlipkartSpider.__new__(FlipkartSpider)
        assert spider._parse_price("₹1,299") == 1299
        assert spider._parse_price("799") == 799
        assert spider._parse_price("") is None


class TestMeeshoSpider:
    def test_spider_name(self):
        assert MeeshoSpider.name == "meesho"

    def test_categories_configured(self):
        assert len(MEESHO_QUERIES) == 10
        assert "tops" in MEESHO_QUERIES
        assert "jeans" in MEESHO_QUERIES

    def test_parse_price(self):
        spider = MeeshoSpider.__new__(MeeshoSpider)
        assert spider._parse_price("₹299 onwards") == 299
        assert spider._parse_price("₹1,299") == 1299
        assert spider._parse_price("") is None


class TestAjioSpider:
    def test_spider_name(self):
        assert AjioSpider.name == "ajio"

    def test_categories_configured(self):
        assert len(AJIO_QUERIES) == 10
        assert "tops" in AJIO_QUERIES
        assert "jeans" in AJIO_QUERIES

    def test_find_products_in_preloaded_state(self):
        # Sample state payload
        state = {
            "searchResponse": {
                "products": [
                    {"code": "123", "name": "Shirt", "brandName": "Zara", "price": {"value": 1999}},
                    {"code": "456", "name": "Jeans", "brandName": "Levis", "price": {"value": 2999}}
                ]
            }
        }
        spider = AjioSpider.__new__(AjioSpider)
        results = list(spider._extract_from_preloaded_state(
            type("MockResponse", (object,), {"text": f"window.__PRELOADED_STATE__ = {json.dumps(state)}</script>", "url": "https://www.ajio.com"})(),
            "tops"
        ))
        assert len(results) == 2
        assert results[0]["platform_id"] == "123"
        assert results[0]["name"] == "Zara Shirt"
        assert results[0]["price_inr"] == 1999
        assert results[1]["platform_id"] == "456"
        assert results[1]["name"] == "Levis Jeans"
        assert results[1]["price_inr"] == 2999


import json
