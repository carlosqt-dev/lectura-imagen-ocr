"""Ubicación, en la plantilla F-LA-08-01, de las 7 celdas que llena el OCR.

Se obtuvo abriendo la plantilla real con openpyxl e inspeccionando celda por
celda (no son coordenadas supuestas). Si la plantilla cambia de versión,
regenere este archivo repitiendo esa inspección (ver README.md de esta
carpeta) en vez de editar los valores a mano.
"""
from __future__ import annotations

NOMBRE_HOJA = "DATOS PRIMARIOS"

# clave interna (tal como la entrega Resultado.como_dict()) -> celda en la hoja
MAPEO_CELDAS: dict[str, str] = {
    "Esfuerzo máximo (MPa)": "D19",
    "Esfuerzo en fluencia (MPa)": "E19",
    "Carga máxima (kN)": "F19",
    "Diámetro probeta (mm)": "G19",
    "Longitud probeta (mm)": "I19",
    "Temperatura (°C)": "G31",
    "Humedad": "L31",
}

# Las columnas D..L de la fila 17 son encabezados dinámicos: cambian según el
# tipo de probeta y el material elegidos en K14/K15 (VLOOKUP contra la tabla
# VARIABLESPROBETA). El mapeo de arriba sólo es válido mientras esas celdas
# sigan diciendo esto (plantilla inspeccionada con K14="Probeta redonda",
# K15="Ferroso"). escribir_resultado() valida esto antes de escribir y avisa
# si no coincide, en vez de escribir en la columna equivocada en silencio.
VALIDACION_ENCABEZADOS: dict[str, tuple[str, str]] = {
    "Esfuerzo máximo (MPa)": ("D17", "Esfuerzo máximo a tracción"),
    "Esfuerzo en fluencia (MPa)": ("E17", "Esfuerzo en el límite de fluencia"),
    "Carga máxima (kN)": ("F17", "Fuerza máxima"),
    "Diámetro probeta (mm)": ("G17", "Diámetro inicial"),
    "Longitud probeta (mm)": ("I17", "Longitud inicial"),
}
