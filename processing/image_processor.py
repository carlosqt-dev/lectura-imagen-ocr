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
    "Humedad", "Temperatura (°C)",
    "Longitud probeta (mm)", "Diámetro probeta (mm)",
    "Carga máxima (kN)", "Esfuerzo máximo (MPa)", "Esfuerzo en fluencia (MPa)",
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

# Algunas líneas de la rejilla (p. ej. el borde entre "No" y "Fecha" en la
# vista de datos) se renderizan en un gris más claro que el resto (~140)
# y no llegan al blanco casi puro (~180-250) de las demás. Un umbral de 155
# las pierde por completo y corre todas las columnas siguientes.
UMBRAL_LINEA = 120

# Separa el trazo (dígitos claros, ~200-255) del fondo de una celda de datos
# (~60-115, con o sin tinte de color en filas resaltadas) para recortar al
# contenido real antes del OCR. Celdas con 1-2 dígitos (p. ej. "Humedad")
# dejan demasiado margen vacío alrededor del glifo si no se recortan, lo que
# hace que Tesseract pierda o invente dígitos de forma errática.
UMBRAL_CONTENIDO = 150
# Fracción de la altura del propio dígito detectado, no un número de píxeles
# fijo: el alto del glifo ya escala solo con el tamaño de fuente que resulte
# de la resolución/escalado de pantalla, así que el margen lo sigue.
MARGEN_CONTENIDO_FRAC = 0.6


@dataclass
class TablaDetectada:
    """Rejilla localizada en una captura: tipo de vista y límites de cada fila/columna."""

    tipo: str
    columnas: tuple[str, ...]
    xs: list[int]
    ys: list[int]
    num_filas: int
    borde: int


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
        """Compatibilidad con el script de línea de comandos: usa la última fila de cada vista."""
        tabla1 = self.detectar_tabla(image1)
        tabla2 = self.detectar_tabla(image2)
        return self.transcribir_fila(image1, tabla1, tabla1.num_filas, image2, tabla2, tabla2.num_filas)

    def detectar_tabla(self, path: str | Path) -> TablaDetectada:
        """Localiza la rejilla y el tipo de vista de una captura, sin leer los valores de las filas."""
        self._verificar_tesseract()
        gray = self._cargar_gray(path)
        xs, ys, inicio, fin, borde = self._rejilla(gray)
        texto = (self._ocr(gray[inicio + borde:fin - borde, xs[0] + borde:xs[-1] - borde], header=True) or "").lower()
        if "fecha" in texto or "hora" in texto:
            tipo, columnas = "datos", VISTA_DATOS
        elif "fluencia" in texto or "rotura" in texto:
            tipo, columnas = "resultados", VISTA_RESULTADOS
        else:
            raise ProcessingError(f"No se identificó la vista en {path}; incluya los encabezados completos.")
        num_filas = len(ys) - 1
        if num_filas < 1:
            raise ProcessingError(f"No se encontraron filas en {path}.")
        return TablaDetectada(tipo=tipo, columnas=columnas, xs=xs, ys=ys, num_filas=num_filas, borde=borde)

    def leer_fila(self, path: str | Path, tabla: TablaDetectada, fila: int) -> dict[str, str | None]:
        """Ejecuta el OCR de los campos requeridos únicamente sobre la fila indicada (1-based)."""
        if not 1 <= fila <= tabla.num_filas:
            raise ProcessingError(f"La fila {fila} no existe en {path} (hay {tabla.num_filas} fila(s)).")
        gray = self._cargar_gray(path)
        arriba, abajo = tabla.ys[fila - 1], tabla.ys[fila]
        borde = tabla.borde
        cells = {
            nombre: self._ocr(gray[arriba + borde:abajo - borde, tabla.xs[j] + borde:tabla.xs[j + 1] - borde])
            for j, nombre in enumerate(tabla.columnas) if nombre in CAMPOS_LECTURA
        }
        if not any(cells.values()):
            raise ProcessingError(f"No se pudo leer la fila {fila} de {path}.")
        return cells

    def transcribir_fila(
        self,
        image1: str | Path, tabla1: TablaDetectada, fila1: int,
        image2: str | Path, tabla2: TablaDetectada, fila2: int,
    ) -> ResultadoProcesado:
        if tabla1.tipo == tabla2.tipo:
            raise ProcessingError("Se necesitan dos vistas distintas: condiciones y resultados mecánicos.")
        if tabla1.tipo == "datos":
            datos_path, datos_tabla, datos_fila = image1, tabla1, fila1
            resultados_path, resultados_tabla, resultados_fila = image2, tabla2, fila2
        else:
            datos_path, datos_tabla, datos_fila = image2, tabla2, fila2
            resultados_path, resultados_tabla, resultados_fila = image1, tabla1, fila1
        datos_celdas = self.leer_fila(datos_path, datos_tabla, datos_fila)
        resultados_celdas = self.leer_fila(resultados_path, resultados_tabla, resultados_fila)
        campos = {
            nombre: datos_celdas.get(nombre) if nombre in datos_celdas else resultados_celdas.get(nombre)
            for nombre in CAMPOS_REQUERIDOS
        }
        pendientes = [k for k, v in campos.items() if v is None]
        avisos = [
            "Selección por posición: se transcribió la fila indicada de cada captura, no un "
            "identificador de ensayo. Verifique que ambas capturas correspondan al mismo "
            "registro y estén en el mismo orden."
        ]
        return ResultadoProcesado(Resultado.desde_texto(campos), avisos, pendientes)

    def _verificar_tesseract(self) -> None:
        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            raise ProcessingError("No se pudo ejecutar Tesseract. Verifique su instalación.") from exc

    def _cargar_gray(self, path: str | Path) -> np.ndarray:
        try:
            contenido = np.fromfile(str(path), dtype=np.uint8)
            image = cv2.imdecode(contenido, cv2.IMREAD_COLOR)
        except Exception as exc:
            raise ProcessingError(f"No se pudo abrir la imagen: {path}") from exc
        if image is None:
            raise ProcessingError(f"No se pudo abrir la imagen: {path}")
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def _rejilla(self, gray: np.ndarray):
        _, ancho = gray.shape
        cobertura_y = np.count_nonzero(gray > UMBRAL_LINEA, axis=1)
        lineas = _centros(np.flatnonzero(cobertura_y >= ancho * 0.80))
        if len(lineas) < 4:
            raise ProcessingError("No se detectaron las líneas horizontales de la tabla.")
        # La altura de fila no se asume en píxeles fijos (eso solo vale para
        # una resolución/escalado de Windows concretos): se autocalibra con
        # la mediana de los huecos entre líneas de ESTA captura. Como la
        # mayoría de los huecos son entre filas (y solo 1-2 son "raros":
        # encabezado, banda vacía), la mediana cae sola sobre la altura real.
        gaps = np.diff(lineas)
        altura_tipica = float(np.median(gaps))
        TOLERANCIA_ALTURA = 0.15
        mejor = []
        for inicio in range(len(lineas) - 1):
            altura = lineas[inicio + 1] - lineas[inicio]
            if abs(altura - altura_tipica) > altura_tipica * TOLERANCIA_ALTURA:
                continue
            secuencia = [lineas[inicio], lineas[inicio + 1]]
            for j in range(inicio + 1, len(lineas) - 1):
                if abs(lineas[j + 1] - lineas[j] - altura) > altura_tipica * TOLERANCIA_ALTURA:
                    break
                secuencia.append(lineas[j + 1])
            if len(secuencia) > len(mejor):
                mejor = secuencia
        if len(mejor) < 4:
            raise ProcessingError("No se identificó una secuencia confiable de filas.")
        anteriores = [y for y in lineas if y < mejor[0]]
        if not anteriores:
            raise ProcessingError("No se detectó el inicio del encabezado.")
        # Recorte para no comerse el trazo de la línea de rejilla: proporcional
        # al tamaño de fila/columna detectado en esta captura, no un número de
        # píxeles fijo (el trazo se renderiza más grueso a mayor resolución).
        BORDE_FRAC = 0.06
        borde = max(1, round(altura_tipica * BORDE_FRAC))
        region = gray[mejor[0] + borde:mejor[-1] - borde, :]
        cobertura_x = np.count_nonzero(region > UMBRAL_LINEA, axis=0)
        xs = _centros(np.flatnonzero(cobertura_x >= region.shape[0] * 0.85))

        # Corrección: excluye franjas externas estrechas, como el borde de la
        # ventana que queda dentro del screenshot completo, si se detectan
        # columnas adicionales. El umbral es proporcional al ancho de columna
        # ya detectado (excluyendo los extremos que se están evaluando), no
        # un número de píxeles fijo: una franja real de borde siempre es una
        # fracción chica del ancho de columna normal, sea cual sea la
        # resolución/escalado de pantalla; una columna real nunca baja de
        # 0.7×normal (ver _validar_anchos_columnas), así que hay margen de
        # sobra entre ambos casos.
        FRANJA_FRAC = 0.4
        while len(xs) > 18:
            anchos_actuales = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
            normal_actual = float(np.median(anchos_actuales[1:-1] or anchos_actuales))
            if xs[-1] - xs[-2] < normal_actual * FRANJA_FRAC:
                xs.pop()
            elif xs[1] - xs[0] < normal_actual * FRANJA_FRAC:
                xs.pop(0)
            else:
                break

        if len(xs) != 18:
            raise ProcessingError(
                f"Se detectaron {max(0, len(xs) - 1)} columnas. "
                "Se esperan las 17 columnas de ELECAV con sus bordes visibles."
            )
        self._validar_anchos_columnas(xs)
        # Una franja vacía bajo la tabla puede tener la misma altura
        # que las filas. Se excluye solo si perdió las divisiones
        # verticales internas, no porque el OCR haya fallado.
        while len(mejor) > 2:
            arriba, abajo = mejor[-2:]
            divisiones = gray[arriba + borde:abajo - borde, xs[1:-1]]
            if divisiones.size == 0:
                raise ProcessingError("La última banda de la rejilla es inválida.")
            soporte = np.mean(divisiones > 155, axis=0)
            if np.mean(soporte >= 0.65) >= 0.60:
                break
            mejor.pop()

        return xs, mejor, anteriores[-1], mejor[0], borde

    def _validar_anchos_columnas(self, xs: list[int]) -> None:
        """Detecta si se perdió o sobró una línea vertical, que corre todas las
        columnas siguientes y hace leer el valor de la columna vecina sin avisar."""
        anchos = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        normal = float(np.median(anchos[1:]))
        if normal <= 0:
            raise ProcessingError("No se pudo medir el ancho de las columnas.")
        if anchos[0] >= normal * 0.9:
            raise ProcessingError(
                "No se detectó el borde entre la columna 'No' y la siguiente; "
                "las columnas quedarían corridas. Repita la captura."
            )
        for posicion, ancho in enumerate(anchos[1:], start=2):
            if not 0.7 * normal <= ancho <= 1.3 * normal:
                raise ProcessingError(
                    f"La columna {posicion} no se alineó correctamente (ancho {ancho}px, "
                    f"se esperaba ~{normal:.0f}px); las columnas quedarían corridas. "
                    "Repita la captura."
                )

    def _ocr(self, crop: np.ndarray, header: bool = False) -> str | None:
        if crop.size == 0:
            return None
        if not header:
            crop = self._recortar_contenido(crop)
            if crop is None:
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

    def _recortar_contenido(self, crop: np.ndarray) -> np.ndarray | None:
        """Recorta la celda al rectángulo real del dígito/símbolo, con un
        margen proporcional a su propio alto, en vez de pasarle a Tesseract
        la celda completa con espacio vacío desproporcionado cuando el
        valor es corto."""
        puntos = cv2.findNonZero((crop > UMBRAL_CONTENIDO).astype(np.uint8))
        if puntos is None:
            return None
        x, y, w, h = cv2.boundingRect(puntos)
        alto, ancho = crop.shape
        margen = max(2, round(h * MARGEN_CONTENIDO_FRAC))
        y0, y1 = max(0, y - margen), min(alto, y + h + margen)
        x0, x1 = max(0, x - margen), min(ancho, x + w + margen)
        return crop[y0:y1, x0:x1]
