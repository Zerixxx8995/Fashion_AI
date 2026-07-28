"""
CV Validator — ml-backend.

Responsibility: Custom validation functions for CV-related requests.
Ensures UUIDs, URLs, lists, and thresholds are formatted correctly.
"""

from __future__ import annotations

import re
from typing import Any, List
from uuid import UUID
from fastapi import HTTPException, status

UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
URL_REGEX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def validate_uuid_string(val: str, field_name: str = "id") -> str:
    """
    Validate that a string is a correctly formatted UUID.

    Raises:
        HTTPException: 422 Unprocessable Entity if invalid.
    """
    if not val:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must not be empty.",
        )
    if not UUID_REGEX.match(val):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Field '{field_name}' must be a valid UUID. Got '{val}'.",
        )
    return val


def validate_image_url(url: str, field_name: str = "url") -> str:
    """
    Validate that a string is a valid HTTP/HTTPS image URL.

    Raises:
        HTTPException: 422 Unprocessable Entity if invalid.
    """
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must not be empty.",
        )
    if not URL_REGEX.match(url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Field '{field_name}' must be a valid HTTP/HTTPS URL. Got '{url}'.",
        )
    return url


def validate_urls_list(urls: List[str], field_name: str = "urls") -> List[str]:
    """
    Validate a list of image URLs. Ensures the list is non-empty and all
    elements are valid URLs.

    Raises:
        HTTPException: 422 Unprocessable Entity if invalid.
    """
    if not urls:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"List '{field_name}' must not be empty.",
        )
    for idx, url in enumerate(urls):
        validate_image_url(url, field_name=f"{field_name}[{idx}]")
    return urls


def validate_detection_threshold(threshold: float) -> float:
    """
    Validate that a similarity or mismatch threshold falls within (0.0, 1.0].

    Raises:
        HTTPException: 422 Unprocessable Entity if invalid.
    """
    if not (0.0 < threshold <= 1.0):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Threshold must be in range (0.0, 1.0]. Got {threshold}.",
        )
    return threshold
