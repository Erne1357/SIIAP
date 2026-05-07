"""
Image processing utilities. Currently used to compress profile photos.

Pillow-based pipeline:
  - Open uploaded image (jpg/png/webp).
  - Auto-orient via EXIF.
  - Convert to RGB (drops alpha; flatten on white background if needed).
  - Resize so the longer side equals target_size (preserve aspect ratio).
  - Save as JPEG with optimize=True and the requested quality.
"""

from io import BytesIO

DEFAULT_TARGET_SIZE = 512
DEFAULT_QUALITY = 85
ALLOWED_INPUT_EXT = {'jpg', 'jpeg', 'png', 'webp'}
MAX_INPUT_BYTES = 5 * 1024 * 1024  # 5 MB


class ImageProcessingError(Exception):
    """Raised when an image cannot be processed."""
    pass


def compress_profile_photo(file_storage,
                            target_size: int = DEFAULT_TARGET_SIZE,
                            quality: int = DEFAULT_QUALITY) -> bytes:
    """
    Compress an uploaded profile photo to JPEG.

    Args:
        file_storage: werkzeug.FileStorage from a multipart upload.
        target_size: longest side, in pixels. Aspect ratio preserved.
        quality: JPEG quality 1-95 (Pillow recommendation).

    Returns:
        bytes of the compressed JPEG image, ready to write to disk.

    Raises:
        ImageProcessingError on invalid/oversized/corrupted input.
    """
    if file_storage is None or not getattr(file_storage, 'filename', ''):
        raise ImageProcessingError("No se recibió ningún archivo.")

    name = (file_storage.filename or '').lower()
    if '.' not in name:
        raise ImageProcessingError("Archivo sin extensión.")
    ext = name.rsplit('.', 1)[1]
    if ext not in ALLOWED_INPUT_EXT:
        raise ImageProcessingError(
            f"Extensión no permitida: {ext}. Permitidas: {', '.join(sorted(ALLOWED_INPUT_EXT))}."
        )

    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size > MAX_INPUT_BYTES:
        raise ImageProcessingError(
            f"La imagen excede el tamaño máximo de {MAX_INPUT_BYTES // (1024 * 1024)} MB."
        )

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ImageProcessingError(
            "Pillow no está instalado. Reconstruye el contenedor con `docker compose build web`."
        ) from exc

    try:
        img = Image.open(stream)
        img = ImageOps.exif_transpose(img)

        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            mask = img.convert('RGBA').split()[-1]
            background.paste(img.convert('RGB'), mask=mask)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        img.thumbnail((target_size, target_size), Image.LANCZOS)

        out = BytesIO()
        img.save(out, format='JPEG', quality=quality, optimize=True, progressive=True)
        return out.getvalue()
    except ImageProcessingError:
        raise
    except Exception as exc:
        raise ImageProcessingError(f"No se pudo procesar la imagen: {exc}") from exc
