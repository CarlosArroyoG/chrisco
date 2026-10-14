import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import InvalidInput

FULL_SIZE = 1600
THUMB_SIZE = 480
_MAX_PIXELS = 40_000_000  # evita "bombas de descompresión"


def _to_jpeg(image: Image.Image, size: int) -> bytes:
    copy = image.copy()
    copy.thumbnail((size, size))
    out = io.BytesIO()
    copy.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


def process_photo(data: bytes) -> tuple[bytes, bytes]:
    """Valida una foto y devuelve (grande, miniatura) como JPEG.

    Se vuelve a codificar siempre: así se descartan metadatos (EXIF con ubicación) y cualquier
    contenido que no sea la imagen en sí. Acepta JPEG, PNG y WebP.
    """
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in {"JPEG", "PNG", "WEBP"}:
                raise InvalidInput("La foto debe ser JPG, PNG o WebP")
            if probe.width * probe.height > _MAX_PIXELS:
                raise InvalidInput("La foto es demasiado grande (más de 40 megapíxeles)")
            image = ImageOps.exif_transpose(probe)  # respeta la orientación de la cámara
            image = image.convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise InvalidInput("El archivo no es una imagen válida") from None
    return _to_jpeg(image, FULL_SIZE), _to_jpeg(image, THUMB_SIZE)
