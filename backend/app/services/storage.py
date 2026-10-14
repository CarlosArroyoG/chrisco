import re
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import InvalidInput
from app.services import images

_KEY_RE = re.compile(r"^[0-9a-f]{32}(-thumb)?\.(pdf|jpg)$")


class PrivateStorage:
    """Archivos en disco. Solo se sirven desde endpoints que deciden quién puede verlos."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(
        self, data: bytes, extension: str, *, base: str | None = None, suffix: str = ""
    ) -> str:
        """Guarda los bytes con una clave aleatoria y devuelve la clave."""
        key = f"{base or uuid.uuid4().hex}{suffix}.{extension}"
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / key).write_bytes(data)
        return key

    def save_pdf(self, data: bytes) -> str:
        return self.save(data, "pdf")

    def save_image(self, full: bytes, thumb: bytes) -> tuple[str, str]:
        """Guarda una foto en dos tamaños con la misma base; devuelve (clave, clave_miniatura)."""
        base = uuid.uuid4().hex
        return (
            self.save(full, "jpg", base=base),
            self.save(thumb, "jpg", base=base, suffix="-thumb"),
        )

    def path(self, key: str) -> Path:
        if not _KEY_RE.match(key):  # evita rutas fuera del directorio
            raise ValueError("Clave de archivo inválida")
        return self.root / key

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.path(key).unlink(missing_ok=True)


@lru_cache
def get_storage() -> PrivateStorage:
    return PrivateStorage(get_settings().uploads_dir)


def read_limited(file: UploadFile) -> bytes:
    """Lee un archivo subido sin pasar del tamaño máximo configurado."""
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise InvalidInput(f"El archivo supera el máximo de {get_settings().max_upload_mb} MB")
    return data


def read_pdf_upload(file: UploadFile) -> bytes:
    """Lee un PDF validando el contenido real (no se confía en la extensión)."""
    data = read_limited(file)
    if not data.startswith(b"%PDF-"):
        raise InvalidInput("El archivo debe ser un PDF")
    return data


def read_document_upload(file: UploadFile) -> tuple[bytes, str]:
    """Lee un documento o comprobante: PDF o foto. Devuelve (bytes, extensión de almacenamiento).

    Las fotos se vuelven a codificar como JPEG (sin metadatos y de tamaño razonable).
    """
    data = read_limited(file)
    if data.startswith(b"%PDF-"):
        return data, "pdf"
    try:
        full, _ = images.process_photo(data)
    except InvalidInput:
        raise InvalidInput("Sube un PDF o una foto (JPG, PNG o WebP)") from None
    return full, "jpg"
