from __future__ import annotations

import base64
import hashlib
import unittest

import numpy as np

from handlers.hiwm.camera import encode_bgr_frame_as_jpeg


class CameraEvidenceTests(unittest.TestCase):
    def test_evidence_hash_covers_exact_jpeg_bytes_sent_to_model(self):
        frame = np.array(
            [
                [[0, 10, 250], [25, 150, 75]],
                [[255, 30, 5], [80, 90, 100]],
            ],
            dtype=np.uint8,
        )
        encoded = encode_bgr_frame_as_jpeg(frame)
        prefix, payload = encoded.data_url.split(",", 1)
        transmitted = base64.b64decode(payload)

        self.assertEqual(prefix, "data:image/jpeg;base64")
        self.assertEqual(transmitted, encoded.jpeg_bytes)
        self.assertEqual(
            encoded.sha256, hashlib.sha256(transmitted).hexdigest()
        )
        self.assertNotEqual(
            encoded.sha256, hashlib.sha256(frame.tobytes()).hexdigest()
        )


if __name__ == "__main__":
    unittest.main()
