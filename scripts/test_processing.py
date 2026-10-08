"""Prueba manual del procesamiento, sin importar PySide6."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from processing import ImageProcessor, ProcessingError


def main() -> int:
    parser = argparse.ArgumentParser(description="Leer la última fila de dos vistas de una tabla")
    parser.add_argument("--image1", required=True, type=Path)
    parser.add_argument("--image2", required=True, type=Path)
    parser.add_argument("--tesseract-cmd", help="Ruta a tesseract.exe si no está en PATH")
    args = parser.parse_args()
    try:
        result = ImageProcessor(args.tesseract_cmd).process(args.image1, args.image2)
    except ProcessingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result.como_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
