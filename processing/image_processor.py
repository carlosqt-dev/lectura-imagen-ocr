"""Lee siete campos de dos vistas complementarias de ELECAV."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from models import Resultado, ResultadoProcesado


class ProcessingError(Exception):
    """No fue posible leer o asociar las capturas."""


CAMPOS_REQUERIDOS = (
    "Esfuerzo máximo (MPa)", "Esfuerzo en fluencia (MPa)",
    "Carga máxima (kN)", "Longitud probeta (mm)",
    "Diámetro probeta (mm)", "Temperatura (°C)", "Humedad",
)
VISTA_DATOS = (
    "No", "Fecha", "Hora", "Validez", "Analista", "Orden trabajo",
    "ID muestra", "ID cliente", "Ingreso", "Humedad", "Temperatura (°C)",
    "Velocidad (MPa/s)", "Longitud probeta (mm)", "Diámetro probeta (mm)",
    "Área (mm²)", "Módulo de Young (MPa)", "Porcentaje módulo (%)",
)
VISTA_RESULTADOS = (
    "No", "Área (mm²)", "Módulo de Young (MPa)", "Porcentaje módulo (%)",
    "Carga máxima (kN)", "Deformación máxima (mm)", "Esfuerzo máximo (MPa)",
    "Elongación máxima (%)", "Deformación en rotura (mm)",
    "Esfuerzo en rotura (MPa)", "Elongación en rotura (%)",
    "Carga en fluencia (N)", "Deformación en fluencia (mm)",
    "Esfuerzo en fluencia (MPa)", "Esfuerzo en límite elástico (MPa)",
    "Esfuerzo de detección (MPa)", "RT_RF",
)
COLUMNAS = CAMPOS_REQUERIDOS
CAMPOS_LECTURA = set(CAMPOS_REQUERIDOS)


@dataclass
class _View:
    tipo: str
    rows: list[dict[str, str | None]]
    warnings: list[str]


def _centros(indices: np.ndarray) -> list[int]:
    if len(indices) == 0:
        return []
    cortes = np.where(np.diff(indices) > 1)[0] + 1
    return [int(round(float(np.mean(g)))) for g in np.split(indices, cortes)]


class ImageProcessor:
    def __init__(self, tesseract_cmd: str | None = None):
        self._tessdata_dir: Path | None = None
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            return
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        bundled = root / "tesseract" / "tesseract.exe"
        if bundled.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(bundled)
            self._tessdata_dir = bundled.parent / "tessdata"
            return
        installed = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if installed.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(installed)

    def process(self, image1: str | Path, image2: str | Path) -> ResultadoProcesado:
        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            raise ProcessingError("No se pudo ejecutar Tesseract. Verifique su instalación.") from exc
        primera, segunda = self._read(image1), self._read(image2)
        if primera.tipo == segunda.tipo:
            raise ProcessingError("Se necesitan dos vistas distintas: condiciones y resultados mecánicos.")
        datos, resultados = (primera, segunda) if primera.tipo == "datos" else (segunda, primera)
        # Modo provisional: toma la última fila de cada vista sin
        # comprobar que ambas correspondan al mismo registro.
        seleccionada = datos.rows[-1]
        mecanicos = resultados.rows[-1]
        campos = {
            nombre: seleccionada.get(nombre) if nombre in seleccionada else mecanicos.get(nombre)
            for nombre in CAMPOS_REQUERIDOS
        }
        pendientes = [k for k, v in campos.items() if v is None]
        avisos = datos.warnings + resultados.warnings + [
            "Validación de correspondencia desactivada temporalmente: "
            "se tomó la última fila de cada captura. Los datos pueden "
            "pertenecer a registros diferentes."
        ]
        return ResultadoProcesado(Resultado.desde_texto(campos), avisos, pendientes)

    def _read(self, path: str | Path) -> _View:
        try:
            contenido = np.fromfile(str(path), dtype=np.uint8)
            image = cv2.imdecode(contenido, cv2.IMREAD_COLOR)
        except Exception as exc:
            raise ProcessingError(f"No se pudo abrir la imagen: {path}") from exc
        if image is None:
            raise ProcessingError(f"No se pudo abrir la imagen: {path}")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        xs, ys, inicio, fin = self._rejilla(gray)
        texto = (self._ocr(gray[inicio + 2:fin - 2, xs[0] + 2:xs[-1] - 2], header=True) or "").lower()
        if "fecha" in texto or "hora" in texto:
            tipo, columnas = "datos", VISTA_DATOS
        elif "fluencia" in texto or "rotura" in texto:
            tipo, columnas = "resultados", VISTA_RESULTADOS
        else:
            raise ProcessingError(f"No se identificó la vista en {path}; incluya los encabezados completos.")
        rows = []
        for numero, (arriba, abajo) in enumerate(zip(ys, ys[1:]), start=1):
            cells = {
                nombre: self._ocr(gray[arriba + 3:abajo - 3, xs[j] + 3:xs[j + 1] - 3])
                for j, nombre in enumerate(columnas) if nombre in CAMPOS_LECTURA
            }
            if not any(cells.values()):
                raise ProcessingError(f"No se pudo leer la fila {numero} de {path}.")
            rows.append(cells)
        if not rows:
            raise ProcessingError(f"No se encontraron filas en {path}.")
        return _View(tipo, rows, [])

    def _rejilla(self, gray: np.ndarray):
        _, ancho = gray.shape
        cobertura_y = np.count_nonzero(gray > 155, axis=1)
        lineas = _centros(np.flatnonzero(cobertura_y >= ancho * 0.80))
        if len(lineas) < 4:
            raise ProcessingError("No se detectaron las líneas horizontales de la tabla.")
        mejor = []
        for inicio in range(len(lineas) - 1):
            altura = lineas[inicio + 1] - lineas[inicio]
            if not 18 <= altura <= 65:
                continue
            secuencia = [lineas[inicio], lineas[inicio + 1]]
            for j in range(inicio + 1, len(lineas) - 1):
                if abs(lineas[j + 1] - lineas[j] - altura) > 4:
                    break
                secuencia.append(lineas[j + 1])
            if len(secuencia) > len(mejor):
                mejor = secuencia
        if len(mejor) < 4:
            raise ProcessingError("No se identificó una secuencia confiable de filas.")
        anteriores = [y for y in lineas if y < mejor[0]]
        if not anteriores:
            raise ProcessingError("No se detectó el inicio del encabezado.")
        region = gray[mejor[0] + 3:mejor[-1] - 3, :]
        cobertura_x = np.count_nonzero(region > 155, axis=0)
        xs = _centros(np.flatnonzero(cobertura_x >= region.shape[0] * 0.85))

        # Corrección: excluye franjas externas estrechas, como la barra
        # de desplazamiento, si se detectan columnas adicionales.
        while len(xs) > 18 and xs[-1] - xs[-2] < 20:
            xs.pop()
        while len(xs) > 18 and xs[1] - xs[0] < 20:
            xs.pop(0)

        if len(xs) != 18:
            raise ProcessingError(
                f"Se detectaron {max(0, len(xs) - 1)} columnas. "
                "Se esperan las 17 columnas de ELECAV con sus bordes visibles."
            )
        # Una franja vacía bajo la tabla puede tener la misma altura
        # que las filas. Se excluye solo si perdió las divisiones
        # verticales internas, no porque el OCR haya fallado.
        while len(mejor) > 2:
            arriba, abajo = mejor[-2:]
            divisiones = gray[arriba + 3:abajo - 3, xs[1:-1]]
            if divisiones.size == 0:
                raise ProcessingError("La última banda de la rejilla es inválida.")
            soporte = np.mean(divisiones > 155, axis=0)
            if np.mean(soporte >= 0.65) >= 0.60:
                break
            mejor.pop()

        return xs, mejor, anteriores[-1], mejor[0]

    def _ocr(self, crop: np.ndarray, header: bool = False) -> str | None:
        if crop.size == 0:
            return None
        large = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        if np.median(large) < 130:
            large = cv2.bitwise_not(large)
        large = cv2.copyMakeBorder(large, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
        config = "--psm 6" if header else "--psm 7 -c tessedit_char_whitelist=0123456789,.-"
        if self._tessdata_dir:
            config += f' --tessdata-dir "{self._tessdata_dir}"'
        texto = pytesseract.image_to_string(large, config=config).strip()
        if header:
            return texto
        texto = re.sub(r"\s+", "", texto)
        return texto if re.fullmatch(r"-?\d+(?:[,.]\d+)?", texto) else None
