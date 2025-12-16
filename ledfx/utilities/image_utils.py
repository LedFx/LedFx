"""Image utility functions for LedFx."""

import logging

import PIL.Image as Image

_LOGGER = logging.getLogger(__name__)


def get_image_metadata(
    abs_path: str,
) -> tuple[int, int, str | None, int, bool]:
    """
    Extract metadata from an image file.

    Args:
        abs_path: Absolute path to the image file

    Returns:
        tuple: (width, height, format, n_frames, is_animated)
            - width: Image width in pixels (0 if cannot read)
            - height: Image height in pixels (0 if cannot read)
            - format: Image format string ('PNG', 'JPEG', 'GIF', 'WEBP', etc.) or None
            - n_frames: Number of frames for animated images (1 for static)
            - is_animated: True if image has multiple frames
    """
    try:
        with Image.open(abs_path) as img:
            width, height = img.size
            img_format = img.format  # 'PNG', 'JPEG', 'GIF', 'WEBP', etc.
            # Get frame count for animated formats (GIF, WebP)
            n_frames = getattr(img, "n_frames", 1)
            is_animated = n_frames > 1
            return width, height, img_format, n_frames, is_animated
    except Exception as e:
        _LOGGER.warning(f"Could not read image metadata for {abs_path}: {e}")
        return 0, 0, None, 1, False
