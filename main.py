import json
import sys
from pathlib import Path

import webview

from ui.api import Api


def main():
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    api = Api()
    window = webview.create_window(
        "Lector de resultados de ensayos",
        str(base_dir / "ui" / "web" / "index.html"),
        js_api=api,
        width=720,
        height=820,
        min_size=(560, 600),
    )
    api.set_window(window)
    webview.start()


def autoprueba(imagen1: str, imagen2: str, salida: str) -> int:
    """Lee la última fila de dos capturas sin abrir la ventana y deja el
    resultado en `salida` (el .exe no tiene consola). Sirve para comprobar el
    OCR embebido en un equipo nuevo sin necesitar ELECAV abierto."""
    from processing import ImageProcessor, ProcessingError

    try:
        datos = {"ok": True, "resultado": ImageProcessor().process(imagen1, imagen2).como_dict()}
    except ProcessingError as exc:
        datos = {"ok": False, "error": str(exc)}
    Path(salida).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if datos["ok"] else 1


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--autoprueba":
        sys.exit(autoprueba(*sys.argv[2:]))
    main()
