"""Camera encoding helpers shared by the handler and API-free tests."""

from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class EncodedJPEGFrame:
    """The exact JPEG representation sent to the multimodal model."""

    jpeg_bytes: bytes
    data_url: str
    sha256: str


def encode_bgr_frame_as_jpeg(
    frame: np.ndarray, *, quality: int = 85
) -> EncodedJPEGFrame:
    """Encode a normalized BGR frame and hash the transmitted JPEG bytes.

    The returned digest deliberately covers ``jpeg_bytes`` rather than the raw
    ndarray. The model receives the base64 representation of these bytes, so
    this is the evidence payload that can actually be reproduced and audited.
    """

    image = Image.fromarray(frame[..., ::-1])
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=quality)
    jpeg_bytes = output.getvalue()
    return EncodedJPEGFrame(
        jpeg_bytes=jpeg_bytes,
        data_url=(
            "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii")
        ),
        sha256=hashlib.sha256(jpeg_bytes).hexdigest(),
    )
