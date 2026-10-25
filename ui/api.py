"""Puente entre la interfaz HTML y la lógica de captura/detección/OCR."""
from __future__ import annotations

import base64
import csv
from pathlib import Path

import webview

from processing import (
    ImageProcessor,
    ProcessingError,
    ScreenCaptureError,
    TablaDetectada,
    capture_elecav_window,
)
from processor_file import ExcelWriteError, escribir_resultado

CAPTURAS_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
PLANTILLA_XLSX = Path(__file__).resolve().parents[1] / (
    "F-LA-08-01 INFORME DE RESULTADOS TRACCIÓN PARA PROBETAS ESTANDAR "
    "(Datos diligenciados).xlsx"
)


def _preview_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


class Api:
    """Expuesta a window.pywebview.api; sus atributos deben empezar con "_".

    pywebview recorre recursivamente los atributos públicos no privados de
    esta instancia para construir el puente JS. Si se guarda aquí el objeto
    `webview.Window` (u otro objeto "vivo" ligado a WebView2) como atributo
    público, esa recorrida termina accediendo a propiedades COM internas
    desde un hilo que no es el de la interfaz y la aplicación se cuelga.
    """

    def __init__(self):
        self._window: webview.Window | None = None
        self._processor = ImageProcessor()
        self._paths: list[Path | None] = [None, None]
        self._tablas: list[TablaDetectada | None] = [None, None]
        self._last_result = None

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    def capturar(self, indice: int) -> dict:
        if indice not in (1, 2):
            return {"ok": False, "error": "Índice de captura inválido.", "preview": None, "tabla": None}
        if self._window is None:
            return {"ok": False, "error": "Ventana no disponible.", "preview": None, "tabla": None}
        try:
            ruta = capture_elecav_window(indice, CAPTURAS_DIR, self._window)
        except ScreenCaptureError as exc:
            return {"ok": False, "error": str(exc), "preview": None, "tabla": None}

        self._paths[indice - 1] = ruta
        self._tablas[indice - 1] = None
        self._last_result = None
        preview = _preview_data_uri(ruta)

        try:
            tabla = self._processor.detectar_tabla(ruta)
        except ProcessingError as exc:
            return {"ok": True, "error": None, "preview": preview, "tabla": {"ok": False, "error": str(exc)}}

        self._tablas[indice - 1] = tabla
        return {
            "ok": True,
            "error": None,
            "preview": preview,
            "tabla": {"ok": True, "error": None, "tipo": tabla.tipo, "num_filas": tabla.num_filas},
        }

    def invalidar_resultado(self) -> dict:
        self._last_result = None
        return {"ok": True}

    def procesar(self, fila: int | str | None = None) -> dict:
        if not all(self._paths):
            return {"ok": False, "error": "Falta tomar las dos capturas antes de transcribir."}
        tabla1, tabla2 = self._tablas
        if tabla1 is None or tabla2 is None:
            return {"ok": False, "error": "No se detectó la tabla en una de las capturas. Repítala."}
        if tabla1.num_filas != tabla2.num_filas:
            return {
                "ok": False,
                "error": (
                    f"Las capturas tienen distinta cantidad de filas "
                    f"({tabla1.num_filas} y {tabla2.num_filas}). Repita una captura antes de transcribir."
                ),
            }
        num_filas = tabla1.num_filas
        if fila in (None, "ultima", ""):
            fila_idx = num_filas
        else:
            try:
                fila_idx = int(fila)
            except (TypeError, ValueError):
                return {"ok": False, "error": "Selección de fila inválida."}
        if not 1 <= fila_idx <= num_filas:
            return {"ok": False, "error": f"La fila {fila_idx} no existe (hay {num_filas})."}

        try:
            resultado = self._processor.transcribir_fila(
                self._paths[0], tabla1, fila_idx, self._paths[1], tabla2, fila_idx
            )
        except ProcessingError as exc:
            self._last_result = None
            return {"ok": False, "error": str(exc)}

        self._last_result = resultado
        return {"ok": True, "resultado": resultado.como_dict(), "fila": fila_idx}

    def exportar_csv(self) -> dict:
        if self._last_result is None:
            return {"ok": False, "error": "Primero transcriba una captura."}
        if self._window is None:
            return {"ok": False, "error": "Ventana no disponible."}
        destino = self._window.create_file_dialog(
            webview.SAVE_DIALOG, directory=str(Path.home()), save_filename="resultado_elecav.csv"
        )
        if not destino:
            return {"ok": False, "error": "Exportación cancelada."}
        ruta = Path(destino if isinstance(destino, str) else destino[0])
        datos = self._last_result.resultado.como_dict()
        with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(["Campo", "Valor"])
            for clave, valor in datos.items():
                escritor.writerow([clave, valor if valor is not None else ""])
        return {"ok": True, "path": str(ruta)}

    def exportar_xlsm(self) -> dict:
        if self._last_result is None:
            return {"ok": False, "error": "Primero transcriba una captura."}
        if self._window is None:
            return {"ok": False, "error": "Ventana no disponible."}
        if not PLANTILLA_XLSX.is_file():
            return {"ok": False, "error": f"No se encontró la plantilla: {PLANTILLA_XLSX.name}"}
        destino = self._window.create_file_dialog(
            webview.SAVE_DIALOG, directory=str(Path.home()), save_filename=PLANTILLA_XLSX.name
        )
        if not destino:
            return {"ok": False, "error": "Exportación cancelada."}
        ruta = Path(destino if isinstance(destino, str) else destino[0])
        try:
            escribir_resultado(self._last_result, PLANTILLA_XLSX, ruta)
        except ExcelWriteError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "path": str(ruta)}
