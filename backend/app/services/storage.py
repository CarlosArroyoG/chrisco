import re
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import InvalidInput

_KEY_RE = re.compile(r"^[0-9a-f]{32}\.pdf$")


class PrivateStorage:
    """Archivos privados en disco. Solo se sirven desde endpoints que comprueban permisos."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save_pdf(self, data: bytes) -> str:
        key = f"{uuid.uuid4().hex}.pdf"
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / key).write_bytes(data)
        return key

    def path(self, key: str) -> Path:
        if not _KEY_RE.match(key):  # evita rutas fuera del directorio
            raise ValueError("Clave de archivo inválida")
        return self.root / key

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)


@lru_cache
def get_storage() -> PrivateStorage:
    return PrivateStorage(get_settings().uploads_dir)


def read_pdf_upload(file: UploadFile) -> bytes:
    """Lee un PDF subido validando tamaño y contenido real (no se confía en la extensión)."""
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise InvalidInput(f"El archivo supera el máximo de {get_settings().max_upload_mb} MB")
    if not data.startswith(b"%PDF-"):
        raise InvalidInput("El archivo debe ser un PDF")
    return data
