"""Revisa los 7 valores transcritos antes de entregarlos al operario: casillas
vacías, valores que no se pudieron leer y valores atípicos (físicamente
imposibles o incoherentes entre sí)."""
from __future__ import annotations

import math

HUMEDAD = "Humedad"
LONGITUD = "Longitud probeta (mm)"
DIAMETRO = "Diámetro probeta (mm)"
CARGA = "Carga máxima (kN)"
ESFUERZO_MAX = "Esfuerzo máximo (MPa)"
ESFUERZO_FLU = "Esfuerzo en fluencia (MPa)"

# En 20 ensayos reales de ELECAV, Esfuerzo máximo = Carga máxima / área de la
# probeta (con el área calculada a partir del Diámetro) se cumplió con un
# error de 0,01% como mucho; los errores de lectura vistos (5 leído como 9,
# coma perdida, etc.) lo rompían entre 11% y 9900%.
TOLERANCIA_COHERENCIA = 0.01


def _numero(texto: str) -> float:
    return float(texto.replace(",", "."))


def revisar(campos: dict[str, str | None], vacios: set[str]) -> list[dict]:
    """Devuelve una alerta por problema: {"campos": [...], "mensaje": str}."""
    alertas = []

    def alertar(nombres: list[str], mensaje: str) -> None:
        alertas.append({"campos": nombres, "mensaje": mensaje})

    for campo, valor in campos.items():
        if valor is None:
            if campo in vacios:
                alertar([campo], f"{campo}: la casilla está vacía en la captura.")
            else:
                alertar([campo], f"{campo}: hay un valor en la casilla pero no se pudo leer; revise la captura.")

    n = {campo: _numero(valor) for campo, valor in campos.items() if valor is not None}

    if HUMEDAD in n and not 0 < n[HUMEDAD] <= 100:
        alertar([HUMEDAD], f"{HUMEDAD}: {campos[HUMEDAD]} % está fuera del rango posible (0 a 100).")
    for campo in (LONGITUD, DIAMETRO, CARGA, ESFUERZO_MAX, ESFUERZO_FLU):
        if campo in n and n[campo] <= 0:
            alertar([campo], f"{campo}: {campos[campo]} debería ser mayor que cero.")

    if n.get(ESFUERZO_MAX, 0) > 0 and n.get(ESFUERZO_FLU, 0) > n[ESFUERZO_MAX]:
        alertar(
            [ESFUERZO_FLU, ESFUERZO_MAX],
            f"El esfuerzo en fluencia ({campos[ESFUERZO_FLU]}) no puede superar al esfuerzo máximo "
            f"({campos[ESFUERZO_MAX]}); uno de los dos está mal leído.",
        )

    if all(n.get(c, 0) > 0 for c in (DIAMETRO, CARGA, ESFUERZO_MAX)):
        area = math.pi * n[DIAMETRO] ** 2 / 4
        esperado = n[CARGA] * 1000 / area
        if abs(esperado - n[ESFUERZO_MAX]) / n[ESFUERZO_MAX] > TOLERANCIA_COHERENCIA:
            alertar(
                [CARGA, DIAMETRO, ESFUERZO_MAX],
                f"Carga máxima, Diámetro y Esfuerzo máximo no cuadran: con {campos[CARGA]} kN y "
                f"{campos[DIAMETRO]} mm el esfuerzo debería ser ~{esperado:.2f} MPa, pero se leyó "
                f"{campos[ESFUERZO_MAX]}. Uno de los tres está mal leído o las dos capturas no son "
                "del mismo registro.",
            )
    return alertas
