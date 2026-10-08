"""Oculta la app, deja que el programa externo quede en primer plano y captura su monitor."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

import win32api
import win32con
import win32gui
from PIL import ImageGrab

ESPERA_ANTES_DE_CAPTURAR_S = 3.0


class ScreenCaptureError(Exception):
    """No fue posible capturar la pantalla externa."""


class VentanaOcultable(Protocol):
    def hide(self) -> None: ...
    def show(self) -> None: ...


def _rect_monitor(hwnd: int) -> tuple[int, int, int, int]:
    monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
    info = win32api.GetMonitorInfo(monitor)
    return info["Monitor"]


def capture_elecav_window(index: int, out_dir: Path, app_window: VentanaOcultable) -> Path:
    """Oculta `app_window`, espera a que el visor/aplicativo externo quede en primer plano
    y captura el monitor donde se encuentra. Restaura `app_window` siempre al terminar."""
    try:
        app_window.hide()
        time.sleep(ESPERA_ANTES_DE_CAPTURAR_S)

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            raise ScreenCaptureError("No se detectó ninguna ventana externa en primer plano.")

        bbox = _rect_monitor(hwnd)
        if bbox[2] - bbox[0] <= 0 or bbox[3] - bbox[1] <= 0:
            raise ScreenCaptureError("No se pudo determinar el monitor de la ventana externa.")

        imagen = ImageGrab.grab(bbox=bbox, all_screens=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        destino = out_dir / f"captura_{index}.png"
        imagen.save(destino)
        return destino
    finally:
        app_window.show()
