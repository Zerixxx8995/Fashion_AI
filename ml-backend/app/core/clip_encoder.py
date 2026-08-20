"""
CLIP Encoder — Pure ML/CV layer.

Responsibility: Generate normalized image and text embeddings using OpenAI's CLIP model.

Rules (enforced by architecture):
  - No HTTP knowledge. No business logic. No database calls.
  - Accepts raw PIL Images or URLs. Returns numpy float32 vectors only.
  - All public functions are pure and stateless — encoder state lives in the
    module-level singleton loaded once at import time.

CLIP model used: openai/clip-vit-base-patch32 (ViT-B/32)
  - Image embedding dimension: 512
  - Text embedding dimension: 512
  - Cosine similarity between image/text embeddings is in range [-1, 1],
    but for real-world fashion images and text it will typically be [0, 1].
"""

from __future__ import annotations

import io
import logging
from functools import lru_cache
from typing import Union

import numpy as np
import requests
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
EMBEDDING_DIM = 512


# ---------------------------------------------------------------------------
# Module-level singleton (loaded once at import time, shared across all calls)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_model() -> tuple[CLIPModel, CLIPProcessor, torch.device]:
    """
    Load CLIP model and processor exactly once.
    Subsequent calls return the cached objects.

    Returns:
        Tuple of (model, processor, device)
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Loading CLIP model '%s' on device '%s'", CLIP_MODEL_ID, device)

    processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
    model = CLIPModel.from_pretrained(CLIP_MODEL_ID).to(device)
    model.eval()  # inference mode — disables dropout, etc.

    logger.info("CLIP model loaded. Embedding dimension: %d", EMBEDDING_DIM)
    return model, processor, device


# ---------------------------------------------------------------------------
# Image loading helpers
# ---------------------------------------------------------------------------

def _load_image_from_url(url: str, timeout: int = 10) -> Image.Image:
    """
    Fetch or open an image from a URL, file:// URI, base64 string, or local path.
    """
    if not url:
        raise ValueError("Image URL or path string is empty.")

    if url.startswith("file://"):
        file_path = url[7:]
        # On Windows file:///C:/... strip extra slash if needed
        if file_path.startswith("/") and len(file_path) > 2 and file_path[2] == ":":
            file_path = file_path[1:]
        try:
            return Image.open(file_path).convert("RGB")
        except Exception as exc:
            raise ValueError(f"Failed to open image file URI '{url}': {exc}") from exc

    if url.startswith("data:image/"):
        import base64
        try:
            header, encoded = url.split(",", 1)
            data = base64.b64decode(encoded)
            return Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as exc:
            raise ValueError(f"Failed to decode base64 image string: {exc}") from exc

    import os
    if os.path.exists(url):
        try:
            return Image.open(url).convert("RGB")
        except Exception as exc:
            raise ValueError(f"Failed to open local image file '{url}': {exc}") from exc

    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        return image
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch image from URL '{url}': {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to decode image from URL '{url}': {exc}") from exc


def _to_pil_image(source: Union[Image.Image, str, bytes]) -> Image.Image:
    """
    Normalise an image source to a PIL Image in RGB mode.

    Args:
        source: A PIL Image, a URL string, or raw image bytes.

    Returns:
        PIL Image in RGB mode.

    Raises:
        TypeError: If the source type is unsupported.
        ValueError: If decoding fails.
    """
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if isinstance(source, str):
        return _load_image_from_url(source)
    if isinstance(source, bytes):
        try:
            return Image.open(io.BytesIO(source)).convert("RGB")
        except Exception as exc:
            raise ValueError(f"Failed to decode image bytes: {exc}") from exc
    raise TypeError(
        f"Unsupported image source type: {type(source).__name__}. "
        "Expected PIL.Image, URL string, or bytes."
    )


# ---------------------------------------------------------------------------
# Public API — pure functions
# ---------------------------------------------------------------------------

def encode_image(source: Union[Image.Image, str, bytes]) -> np.ndarray:
    """
    Generate a normalized CLIP image embedding.

    The returned vector has L2 norm = 1. Cosine similarity between two
    normalized vectors is just their dot product, which is fast and exact.

    Args:
        source: A PIL Image, a public URL string, or raw image bytes.

    Returns:
        numpy float32 array of shape (512,) — the image embedding, L2-normalized.

    Example:
        >>> embedding = encode_image("https://example.com/shirt.jpg")
        >>> embedding.shape
        (512,)
        >>> import numpy as np
        >>> np.isclose(np.linalg.norm(embedding), 1.0)
        True
    """
    model, processor, device = _load_model()
    image = _to_pil_image(source)

    with torch.no_grad():
        inputs = processor(images=image, return_tensors="pt").to(device)
        # Use vision_model + pooler to get a plain tensor (stable across transformers v4 & v5)
        vision_outputs = model.vision_model(**inputs)
        features = model.visual_projection(vision_outputs.pooler_output)
        # L2-normalize so cosine similarity = dot product
        features = features / features.norm(dim=-1, keepdim=True)

    return features.squeeze(0).cpu().numpy().astype(np.float32)


def encode_text(text: str) -> np.ndarray:
    """
    Generate a normalized CLIP text embedding.

    The returned vector has L2 norm = 1, matching the scale of encode_image
    embeddings, so cross-modal cosine similarity works directly.

    Args:
        text: A natural language string describing a fashion item
              (e.g. "red cotton kurta with embroidery").

    Returns:
        numpy float32 array of shape (512,) — the text embedding, L2-normalized.

    Example:
        >>> embedding = encode_text("blue denim jacket")
        >>> embedding.shape
        (512,)
    """
    if not text or not text.strip():
        raise ValueError("Text input must not be empty.")

    model, processor, device = _load_model()

    with torch.no_grad():
        inputs = processor(text=[text], return_tensors="pt", truncation=True).to(device)
        # Use text_model + projection to get a plain tensor (stable across transformers v4 & v5)
        text_outputs = model.text_model(**inputs)
        features = model.text_projection(text_outputs.pooler_output)
        features = features / features.norm(dim=-1, keepdim=True)

    return features.squeeze(0).cpu().numpy().astype(np.float32)


def encode_images_batch(
    sources: list[Union[Image.Image, str, bytes]],
    batch_size: int = 32,
) -> np.ndarray:
    """
    Encode a list of images in batches for efficiency.

    Args:
        sources: List of image sources (PIL Images, URL strings, or bytes).
        batch_size: Number of images to process in each forward pass.

    Returns:
        numpy float32 array of shape (N, 512), L2-normalized row-wise.

    Raises:
        ValueError: If sources list is empty.
    """
    if not sources:
        raise ValueError("Sources list must not be empty.")

    model, processor, device = _load_model()
    all_embeddings: list[np.ndarray] = []

    for i in range(0, len(sources), batch_size):
        batch = [_to_pil_image(s) for s in sources[i : i + batch_size]]
        with torch.no_grad():
            inputs = processor(images=batch, return_tensors="pt").to(device)
            vision_outputs = model.vision_model(**inputs)
            features = model.visual_projection(vision_outputs.pooler_output)
            features = features / features.norm(dim=-1, keepdim=True)
            all_embeddings.append(features.cpu().numpy().astype(np.float32))

    return np.vstack(all_embeddings)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two L2-normalized embedding vectors.

    Because encode_image and encode_text always return L2-normalized vectors,
    cosine similarity is simply the dot product — O(d) with no division needed.

    Args:
        vec_a: L2-normalized float32 array of shape (512,).
        vec_b: L2-normalized float32 array of shape (512,).

    Returns:
        Cosine similarity as a Python float in range [-1.0, 1.0].
        For same-domain fashion embeddings this is typically in [0.0, 1.0].

    Raises:
        ValueError: If vectors have mismatched shapes.
    """
    if vec_a.shape != vec_b.shape:
        raise ValueError(
            f"Shape mismatch: vec_a={vec_a.shape}, vec_b={vec_b.shape}"
        )
    # Both vectors are pre-normalised, so dot product = cosine similarity
    similarity = float(np.dot(vec_a, vec_b))
    # Clamp to [-1, 1] to correct for floating-point rounding beyond unit sphere
    return max(-1.0, min(1.0, similarity))
