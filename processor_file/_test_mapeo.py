"""Valida el mapeo de celdas de forma aislada, sin pasar por el OCR.

Uso: python -m processor_file._test_mapeo
Abre la plantilla real del proyecto, escribe un Resultado de ejemplo y
guarda la copia en data/processed/_test_mapeo_salida.xlsx para revisarla
a mano (o abrirla en Excel) y confirmar que cada valor cayó en la celda
correcta.
"""
from __future__ import annotations

import logging
from pathlib import Path

from models import Resultado, ResultadoProcesado

from .excel_writer import escribir_resultado

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA = RAIZ / (
    "F-LA-08-01 INFORME DE RESULTADOS TRACCIÓN PARA PROBETAS ESTANDAR "
    "(Datos diligenciados).xlsx"
)
SALIDA = RAIZ / "data" / "processed" / "_test_mapeo_salida.xlsx"


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    datos_prueba = {
        "Humedad": "55",
        "Temperatura (°C)": "21,5",
        "Longitud probeta (mm)": "50,25",
        "Diámetro probeta (mm)": "12,68",
        "Carga máxima (kN)": "90,10",
        "Esfuerzo máximo (MPa)": "700,00",
        "Esfuerzo en fluencia (MPa)": "380,20",
    }
    resultado = ResultadoProcesado(
        resultado=Resultado.desde_texto(datos_prueba),
        avisos=[],
        campos_pendientes=[],
    )

    ruta = escribir_resultado(resultado, PLANTILLA, SALIDA)
    print(f"Archivo de prueba guardado en: {ruta}")


if __name__ == "__main__":
    main()
