"""Escribe el esquema OpenAPI a un archivo. De él se generan los tipos del frontend.

Uso: uv run python -m app.export_openapi ../frontend/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m app.export_openapi <archivo-de-salida>")
    Path(sys.argv[1]).write_text(
        json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
