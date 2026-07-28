"""
Tests for validators — ml-backend.

Asserts:
  - Valid input passes through validators unchanged.
  - Invalid inputs raise HTTPException with 422 status code.
  - Correct detail messages are returned.
"""

from __future__ import annotations

import io
from fastapi import HTTPException, UploadFile
import pytest
from PIL import Image

from app.validators import (
    validate_uuid_string,
    validate_image_url,
    validate_urls_list,
    validate_detection_threshold,
    validate_image_file,
)


class TestCVValidator:
    """Tests for core CV input validators."""

    # 1. UUID Validation
    def test_validate_uuid_string_success(self):
        valid_uuid = "c8b4df56-e918-4b72-8f52-64f33b1e3271"
        assert validate_uuid_string(valid_uuid) == valid_uuid

    def test_validate_uuid_string_failure_format(self):
        invalid_uuid = "not-a-uuid"
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid_string(invalid_uuid)
        assert exc_info.value.status_code == 422
        assert "must be a valid UUID" in exc_info.value.detail

    def test_validate_uuid_string_failure_empty(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid_string("")
        assert exc_info.value.status_code == 422
        assert "must not be empty" in exc_info.value.detail

    # 2. URL Validation
    def test_validate_image_url_success(self):
        valid_url = "https://example.com/image.jpg"
        assert validate_image_url(valid_url) == valid_url

    def test_validate_image_url_failure_format(self):
        invalid_url = "ftp://bad-scheme.com/img.png"
        with pytest.raises(HTTPException) as exc_info:
            validate_image_url(invalid_url)
        assert exc_info.value.status_code == 422
        assert "must be a valid HTTP/HTTPS URL" in exc_info.value.detail

    def test_validate_image_url_failure_empty(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_image_url("")
        assert exc_info.value.status_code == 422
        assert "must not be empty" in exc_info.value.detail

    # 3. URLs List Validation
    def test_validate_urls_list_success(self):
        urls = ["https://site.com/1.png", "http://site.com/2.jpg"]
        assert validate_urls_list(urls) == urls

    def test_validate_urls_list_failure_empty(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_urls_list([])
        assert exc_info.value.status_code == 422
        assert "must not be empty" in exc_info.value.detail

    def test_validate_urls_list_failure_contains_invalid(self):
        urls = ["https://site.com/1.png", "not-a-url"]
        with pytest.raises(HTTPException) as exc_info:
            validate_urls_list(urls)
        assert exc_info.value.status_code == 422
        assert "must be a valid HTTP/HTTPS URL" in exc_info.value.detail

    # 4. Threshold Validation
    def test_validate_detection_threshold_success(self):
        assert validate_detection_threshold(0.45) == 0.45
        assert validate_detection_threshold(1.0) == 1.0

    def test_validate_detection_threshold_failure_low(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_detection_threshold(0.0)
        assert exc_info.value.status_code == 422
        assert "must be in range (0.0, 1.0]" in exc_info.value.detail

    def test_validate_detection_threshold_failure_negative(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_detection_threshold(-0.1)
        assert exc_info.value.status_code == 422

    def test_validate_detection_threshold_failure_high(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_detection_threshold(1.05)
        assert exc_info.value.status_code == 422


class TestImageValidator:
    """Tests for image file validation."""

    def _make_mock_upload_file(
        self, filename: str, content_type: str, data: bytes
    ) -> UploadFile:
        from starlette.datastructures import Headers
        headers = Headers({"content-type": content_type})
        return UploadFile(
            filename=filename,
            file=io.BytesIO(data),
            headers=headers,
            size=len(data),
        )

    def test_validate_image_file_success(self):
        # Create a tiny valid JPEG image in memory
        f = io.BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(f, format="JPEG")
        data = f.getvalue()

        file = self._make_mock_upload_file("test_image.jpg", "image/jpeg", data)

        # Should pass without exception
        validate_image_file(file)

    def test_validate_image_file_failure_no_name(self):
        file = self._make_mock_upload_file("", "image/png", b"data")
        with pytest.raises(HTTPException) as exc_info:
            validate_image_file(file)
        assert exc_info.value.status_code == 422
        assert "File has no name" in exc_info.value.detail

    def test_validate_image_file_failure_extension(self):
        file = self._make_mock_upload_file("document.pdf", "application/pdf", b"data")
        with pytest.raises(HTTPException) as exc_info:
            validate_image_file(file)
        assert exc_info.value.status_code == 422
        assert "Unsupported file extension" in exc_info.value.detail

    def test_validate_image_file_failure_mime_type(self):
        file = self._make_mock_upload_file("photo.jpg", "text/plain", b"data")
        with pytest.raises(HTTPException) as exc_info:
            validate_image_file(file)
        assert exc_info.value.status_code == 422
        assert "Unsupported MIME type" in exc_info.value.detail

    def test_validate_image_file_failure_empty(self):
        file = self._make_mock_upload_file("empty.png", "image/png", b"")
        with pytest.raises(HTTPException) as exc_info:
            validate_image_file(file)
        assert exc_info.value.status_code == 422
        assert "File is empty" in exc_info.value.detail

    def test_validate_image_file_failure_too_large(self):
        # 6MB of noise
        data = b"\x00" * (6 * 1024 * 1024)
        file = self._make_mock_upload_file("large.png", "image/png", data)
        with pytest.raises(HTTPException) as exc_info:
            validate_image_file(file)
        assert exc_info.value.status_code == 422
        assert "exceeds limit" in exc_info.value.detail

    def test_validate_image_file_failure_corrupt(self):
        # PDF data named as PNG
        data = b"%PDF-1.4 header contents..."
        file = self._make_mock_upload_file("fake_photo.png", "image/png", data)
        with pytest.raises(HTTPException) as exc_info:
            validate_image_file(file)
        assert exc_info.value.status_code == 422
        assert "Corrupt or invalid image file" in exc_info.value.detail
