"""Lee siete campos de dos vistas complementarias de ELECAV."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
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

# Las columnas se identifican por su encabezado y no por su posición fija:
# ELECAV ensancha columnas según el texto (p. ej. "ID cliente"), así que a
# veces no entran las 17 y la tabla puede verse sin su borde izquierdo.
# Solo se usan palabras de las primeras líneas del encabezado (sin tildes, en
# minúscula): la 3.ª suele quedar cortada y Tesseract la lee como basura
# ("Fluencia" -> "eliansia"). Una columna sin claves no sirve de ancla; se
# ubica por su posición respecto de las anclas, porque ELECAV siempre
# muestra las columnas en el mismo orden.
CLAVES_DATOS = {
    "Fecha": ("fecha",), "Hora": ("hora",), "Validez": ("validez",),
    "Analista": ("analista",), "Orden trabajo": ("orden",), "ID muestra": ("muestra",),
    "ID cliente": ("cliente",), "Ingreso": ("ingreso",), "Humedad": ("humedad",),
    "Temperatura (°C)": ("peratur",), "Velocidad (MPa/s)": ("velocidad",),
    "Longitud probeta (mm)": ("longitud",), "Diámetro probeta (mm)": ("metro",),
    "Área (mm²)": ("area",), "Módulo de Young (MPa)": ("young",),
    "Porcentaje módulo (%)": ("porcentaje",),
}
CLAVES_RESULTADOS = {
    "Área (mm²)": ("area",), "Módulo de Young (MPa)": ("young",),
    "Porcentaje módulo (%)": ("porcentaje",), "Carga máxima (kN)": ("carga", "maxim"),
    "Deformación máxima (mm)": ("formac", "maxim"), "Esfuerzo máximo (MPa)": ("esfuerzo", "maxim"),
    "Elongación máxima (%)": ("elongac", "maxim"), "Carga en fluencia (N)": ("carga", "fluencia"),
    "Esfuerzo en límite elástico (MPa)": ("esfuerzo", "limite"),
    "Esfuerzo de detección (MPa)": ("esfuerzo de",), "RT_RF": ("rtrf",),
}
VISTAS = {"datos": (VISTA_DATOS, CLAVES_DATOS), "resultados": (VISTA_RESULTADOS, CLAVES_RESULTADOS)}
# Comprobación mínima del encabezado de un campo requerido que no tiene claves
# propias (su palabra distintiva está en la línea cortada).
VERIFICAR_ENCABEZADO = {"Esfuerzo en fluencia (MPa)": ("esfuerzo",)}
MIN_ANCLAS = 3

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

# Altos (px) a los que se lleva el dígito antes de pasarlo a Tesseract, en vez
# de un factor de ampliación fijo: los dígitos de ELECAV miden ~15 px en una
# captura y ~19 px en otra según la pantalla, y Tesseract lee mejor con
# glifos de ~30 px (con 3x/5x fijo quedaban de 45-95 px y confundía 5 con 9).
# Aun así, a un alto puntual a veces confunde un dígito (7 -> 1) que a los
# altos vecinos lee bien, así que se lee a los tres y se exige que al menos
# dos coincidan. Sobre 305 valores reales: cada alto suelto 304/305; votando
# 305/305, sin ningún valor dejado como pendiente.
ALTOS_DIGITO = (28, 30, 32)

# Una lectura normal tarda <1 s; si tesseract.exe se cuelga, se mata el
# proceso al vencer el plazo en vez de dejar la app esperando para siempre.
TIMEOUT_OCR_S = 15


@dataclass
class TablaDetectada:
    """Rejilla localizada en una captura: tipo de vista y límites de cada fila/columna."""

    tipo: str
    # Campo requerido -> índice j de su columna (celda entre xs[j] y xs[j + 1]).
    campos: dict[str, int]
    xs: list[int]
    ys: list[int]
    num_filas: int
    borde: int


def _centros(indices: np.ndarray) -> list[int]:
    if len(indices) == 0:
        return []
    cortes = np.where(np.diff(indices) > 1)[0] + 1
    return [int(round(float(np.mean(g)))) for g in np.split(indices, cortes)]


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )
    return " ".join("".join(c for c in sin_tildes if c.isalnum() or c.isspace()).split())


class ImageProcessor:
    def __init__(self, tesseract_cmd: str | None = None):
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        bundled = root / "tesseract" / "tesseract.exe"
        installed = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if tesseract_cmd:
            self._tesseract = tesseract_cmd
        elif bundled.is_file():
            self._tesseract = str(bundled)
        elif installed.is_file():
            self._tesseract = str(installed)
        else:
            self._tesseract = "tesseract"
        # Tesseract (build MinGW) falla con "Illegal byte sequence" si resuelve
        # su carpeta tessdata como ruta absoluta con tildes o "ñ" (p. ej. si la
        # app quedó en C:\Users\José\Escritorio). Se lo lanza desde su propia
        # carpeta con la ruta relativa, que no pasa por esa conversión, y de
        # paso se ignora un TESSDATA_PREFIX de otra instalación del equipo.
        carpeta = Path(self._tesseract).parent
        if (carpeta / "tessdata").is_dir():
            self._cwd: Path | None = carpeta
            self._env: dict[str, str] | None = {**os.environ, "TESSDATA_PREFIX": "tessdata"}
        else:
            self._cwd = None
            self._env = None

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
        num_filas = len(ys) - 1
        if num_filas < 1:
            raise ProcessingError(f"No se encontraron filas en {path}.")
        celdas = [gray[inicio + borde:fin - borde, xs[j] + borde:xs[j + 1] - borde] for j in range(len(xs) - 1)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            encabezados = [_normalizar(t or "") for t in pool.map(lambda c: self._ocr(c, header=True), celdas)]
        tipo, campos = self._ubicar_campos(encabezados, xs, path)
        return TablaDetectada(tipo=tipo, campos=campos, xs=xs, ys=ys, num_filas=num_filas, borde=borde)

    def _ubicar_campos(self, encabezados: list[str], xs: list[int], path: str | Path) -> tuple[str, dict[str, int]]:
        """Decide la vista y la columna de cada campo requerido a partir de los
        encabezados que se reconocen sin ambigüedad (anclas)."""
        elegida = None
        for tipo, (vista, claves) in VISTAS.items():
            anclas = []  # (columna detectada, posición en la vista de ELECAV)
            for j, texto in enumerate(encabezados):
                nombres = [n for n, palabras in claves.items() if all(p in texto for p in palabras)]
                if len(nombres) == 1:
                    anclas.append((j, vista.index(nombres[0])))
            if anclas:
                desfase, votos = Counter(pos - j for j, pos in anclas).most_common(1)[0]
                if elegida is None or votos > elegida[1]:
                    elegida = (tipo, votos, desfase, anclas)
        if elegida is None or elegida[1] < MIN_ANCLAS:
            raise ProcessingError(f"No se identificó la vista en {path}; incluya los encabezados de la tabla.")
        tipo, _, desfase, anclas = elegida
        vista, claves = VISTAS[tipo]
        if any(pos - j != desfase for j, pos in anclas):
            # Una ancla fuera de lugar indica que falta o sobra una línea
            # vertical en medio: leer por posición tomaría la columna vecina.
            raise ProcessingError(
                "Los encabezados de la tabla no quedaron en el orden esperado (falta o sobra "
                "una línea de la tabla). Repita la captura."
            )
        anchos = np.diff(xs)
        normal = float(np.median(anchos))
        campos = {}
        for nombre in CAMPOS_REQUERIDOS:
            if nombre not in vista:
                continue
            j = vista.index(nombre) - desfase
            if not 0 <= j < len(anchos):
                raise ProcessingError(
                    f"La columna '{nombre}' no se ve en la captura. Desplace la tabla en ELECAV "
                    "para que quede visible y repita la captura."
                )
            if not 0.7 * normal <= anchos[j] <= 1.3 * normal:
                raise ProcessingError(
                    f"La columna '{nombre}' quedó cortada o mal delimitada en la captura. "
                    "Repita la captura."
                )
            palabras = claves.get(nombre) or VERIFICAR_ENCABEZADO[nombre]
            if not all(p in encabezados[j] for p in palabras):
                raise ProcessingError(
                    f"No se pudo confirmar la columna '{nombre}' por su encabezado. Repita la captura."
                )
            campos[nombre] = j
        return tipo, campos

    def leer_fila(self, path: str | Path, tabla: TablaDetectada, fila: int) -> dict[str, str | None]:
        """Ejecuta el OCR de los campos requeridos únicamente sobre la fila indicada (1-based)."""
        if not 1 <= fila <= tabla.num_filas:
            raise ProcessingError(f"La fila {fila} no existe en {path} (hay {tabla.num_filas} fila(s)).")
        gray = self._cargar_gray(path)
        arriba, abajo = tabla.ys[fila - 1], tabla.ys[fila]
        borde = tabla.borde
        celdas = [gray[arriba + borde:abajo - borde, tabla.xs[j] + borde:tabla.xs[j + 1] - borde]
                  for j in tabla.campos.values()]
        with ThreadPoolExecutor(max_workers=4) as pool:
            cells = dict(zip(tabla.campos, pool.map(self._ocr, celdas)))
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
        self._ejecutar_tesseract("--version")

    def _ejecutar_tesseract(self, *args: str, imagen: np.ndarray | None = None) -> str:
        """Corre tesseract.exe sin ventana; la imagen va por stdin (sin archivo
        temporal). Si se cuelga, subprocess.run lo mata al vencer el timeout."""
        entrada = None
        if imagen is not None:
            entrada = cv2.imencode(".png", imagen)[1].tobytes()
            args = ("-", "stdout", *args)
        try:
            r = subprocess.run(
                [self._tesseract, *args],
                input=entrada,
                capture_output=True,
                cwd=self._cwd,
                env=self._env,
                timeout=TIMEOUT_OCR_S,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise ProcessingError(f"Tesseract no respondió en {TIMEOUT_OCR_S} s.") from exc
        except OSError as exc:
            raise ProcessingError("No se pudo ejecutar Tesseract. Verifique su instalación.") from exc
        if r.returncode != 0:
            detalle = r.stderr.decode("utf-8", "replace").strip()
            raise ProcessingError(f"Tesseract no pudo leer la imagen: {detalle}")
        return r.stdout.decode("utf-8", "replace")

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
        # No se exige un número fijo de columnas ni anchos parecidos: las
        # columnas se identifican después por su encabezado (_ubicar_campos).
        # Franjas sobrantes (barra de desplazamiento, borde de ventana) quedan
        # como columnas sin encabezado reconocible y no se usan.
        if len(xs) < 4:
            raise ProcessingError("No se detectaron las líneas verticales de la tabla.")
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

    def _ocr(self, crop: np.ndarray, header: bool = False) -> str | None:
        if crop.size == 0:
            return None
        if header:
            return self._leer(crop, 3, header=True)
        recorte = self._recortar_contenido(crop)
        if recorte is None:
            return None
        crop, alto_digito = recorte
        lecturas = Counter(
            v for v in (self._leer(crop, alto / alto_digito) for alto in ALTOS_DIGITO) if v is not None
        )
        if not lecturas:
            return None
        valor, votos = lecturas.most_common(1)[0]
        # Sin al menos dos lecturas iguales el valor queda pendiente para que
        # el operario lo revise, en vez de adivinar.
        return valor if votos >= 2 else None

    def _leer(self, crop: np.ndarray, escala: float, header: bool = False) -> str | None:
        interpolacion = cv2.INTER_AREA if escala < 1 else cv2.INTER_CUBIC
        large = cv2.resize(crop, None, fx=escala, fy=escala, interpolation=interpolacion)
        if np.median(large) < 130:
            large = cv2.bitwise_not(large)
        if not header:
            # Blanco y negro puro: elimina los grises del antialiasing que
            # hacían que el "5" se leyera como "9" (sin esto: 191/210).
            _, large = cv2.threshold(large, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        large = cv2.copyMakeBorder(large, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
        if header:
            args = ("--psm", "6")
        else:
            args = ("--psm", "7", "-c", "tessedit_char_whitelist=0123456789,.-")
        texto = self._ejecutar_tesseract(*args, imagen=large).strip()
        if header:
            return texto
        texto = re.sub(r"\s+", "", texto)
        return texto if re.fullmatch(r"-?\d+(?:[,.]\d+)?", texto) else None

    def _recortar_contenido(self, crop: np.ndarray) -> tuple[np.ndarray, int] | None:
        """Recorta la celda al rectángulo real del dígito/símbolo, con un
        margen proporcional a su propio alto, en vez de pasarle a Tesseract
        la celda completa con espacio vacío desproporcionado cuando el
        valor es corto. Devuelve el recorte y el alto del contenido.

        Solo cuentan las manchas que pueden ser caracteres. Se ignoran los
        puntos sueltos (línea punteada de la fila seleccionada en ELECAV), las
        líneas o franjas que cruzan casi toda la celda (borde de la barra de
        desplazamiento bajo la última fila) y las líneas verticales de borde:
        si entraran, inflarían el alto del "dígito", el número se escalaría de
        menos y Tesseract perdía o deformaba la coma."""
        mascara = (crop > UMBRAL_CONTENIDO).astype(np.uint8)
        alto, ancho = crop.shape
        # Una fila o columna de píxeles encendida casi entera es una línea o
        # franja, no un carácter. Se borra antes de separar manchas porque la
        # coma y la base de los números suelen tocarla y quedarían fusionados.
        filas_linea = mascara.mean(axis=1) >= 0.8
        cols_linea = mascara.mean(axis=0) >= 0.8
        mascara[filas_linea, :] = 0
        mascara[:, cols_linea] = 0
        _, _, stats, _ = cv2.connectedComponentsWithStats(mascara, connectivity=8)
        # Puntos sueltos solo si tocan el borde de arriba o de abajo (línea
        # punteada de la fila seleccionada); los del medio pueden ser partes
        # de la coma y cuentan para el alto, con el que se calibró la escala.
        cajas = [
            (x, y, w, h) for x, y, w, h, _ in stats[1:]
            if not (w <= 3 and h <= 2 and (y == 0 or y + h >= alto))
        ]
        if not cajas:
            return None
        x, y = min(c[0] for c in cajas), min(c[1] for c in cajas)
        w = max(c[0] + c[2] for c in cajas) - x
        h = max(c[1] + c[3] for c in cajas) - y
        if filas_linea.any() or cols_linea.any():
            crop = crop.copy()
            fondo = int(np.median(crop))
            crop[filas_linea, :] = fondo
            crop[:, cols_linea] = fondo
        margen = max(2, round(h * MARGEN_CONTENIDO_FRAC))
        y0, y1 = max(0, y - margen), min(alto, y + h + margen)
        x0, x1 = max(0, x - margen), min(ancho, x + w + margen)
        return crop[y0:y1, x0:x1], h
