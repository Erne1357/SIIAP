# tests/profile/test_image_processing.py
"""
Tests for app.utils.image_processing.compress_profile_photo:
  - Compresses to JPEG bytes
  - Resizes large images so longer side <= target_size
  - Rejects unsupported extensions
  - Rejects oversized files
"""

import io
import unittest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.utils.image_processing import (
    compress_profile_photo, ImageProcessingError,
)


def _make_filestorage(filename, fmt='JPEG', size=(1024, 768), color=(120, 120, 120),
                       padding_bytes: int = 0):
    img = Image.new('RGB', size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    if padding_bytes > 0:
        buf.write(b'\x00' * padding_bytes)
    buf.seek(0)
    return FileStorage(stream=buf, filename=filename)


class TestCompressProfilePhoto(unittest.TestCase):

    def test_returns_jpeg_bytes(self):
        fs = _make_filestorage('photo.jpg', fmt='JPEG', size=(900, 600))
        out = compress_profile_photo(fs)
        self.assertIsInstance(out, bytes)
        # JPEG magic header
        self.assertEqual(out[:3], b'\xff\xd8\xff')

    def test_resizes_to_target(self):
        fs = _make_filestorage('photo.jpg', fmt='JPEG', size=(2000, 1500))
        out = compress_profile_photo(fs, target_size=512)
        img = Image.open(io.BytesIO(out))
        self.assertLessEqual(max(img.size), 512)

    def test_small_image_not_upscaled(self):
        fs = _make_filestorage('photo.jpg', fmt='JPEG', size=(100, 80))
        out = compress_profile_photo(fs, target_size=512)
        img = Image.open(io.BytesIO(out))
        self.assertEqual(max(img.size), 100)

    def test_png_input_supported(self):
        fs = _make_filestorage('photo.png', fmt='PNG', size=(800, 800))
        out = compress_profile_photo(fs)
        self.assertEqual(out[:3], b'\xff\xd8\xff')

    def test_invalid_extension_rejected(self):
        fs = _make_filestorage('photo.bmp', fmt='BMP', size=(400, 400))
        with self.assertRaises(ImageProcessingError):
            compress_profile_photo(fs)

    def test_file_without_extension_rejected(self):
        fs = _make_filestorage('photo', fmt='JPEG', size=(400, 400))
        with self.assertRaises(ImageProcessingError):
            compress_profile_photo(fs)

    def test_none_filestorage_rejected(self):
        with self.assertRaises(ImageProcessingError):
            compress_profile_photo(None)

    def test_oversized_input_rejected(self):
        # Build a JPEG and pad with 6 MB of zeros to push past the 5 MB limit
        fs = _make_filestorage(
            'photo.jpg', fmt='JPEG', size=(400, 400),
            padding_bytes=6 * 1024 * 1024,
        )
        with self.assertRaises(ImageProcessingError):
            compress_profile_photo(fs)


if __name__ == '__main__':
    unittest.main()
