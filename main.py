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


if __name__ == "__main__":
    main()
