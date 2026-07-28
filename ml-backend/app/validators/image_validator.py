"""
Image Validator — ml-backend.

Responsibility: Validate user-uploaded image files for computer vision tasks.
Ensures file size, extensions, MIME types, and image integrity are correct.
"""

from __future__ import annotations

import io
import os
from fastapi import HTTPException, UploadFile, status
from PIL import Image

# Configuration
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_image_file(file: UploadFile) -> None:
    """
    Validate an uploaded image file.

    Checks:
      - Non-empty filename and allowed extension
      - Allowed MIME content type
      - File size matches limit (<= 5MB)
      - Image file is readable and not corrupt

    Raises:
        HTTPException: 422 Unprocessable Entity if validation fails.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File has no name.",
        )

    # 1. Extension Check
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Content Type Check
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported MIME type '{file.content_type}'. Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    # 3. File Size Check
    # Move cursor to end to determine size
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)  # Reset cursor for reading

    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is empty.",
        )

    if size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        size_mb = size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File size ({size_mb:.2f}MB) exceeds limit of {max_mb:.1f}MB.",
        )

    # 4. Image Integrity Check
    try:
        content = file.file.read()
        file.file.seek(0)  # Reset cursor
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Corrupt or invalid image file. Details: {str(exc)}",
        )
