# Lector de resultados (prototipo)

## Estructura

```text
lector_tabla/
├── main.py                        # inicia la ventana pywebview
├── models/result.py               # resultado y avisos
├── processing/image_processor.py  # rejilla, OCR, selección y comparación
├── processing/screen_capture.py   # oculta la app y captura el monitor externo
├── ui/api.py                      # puente entre el HTML y Python (js_api)
├── ui/web/                        # interfaz (index.html, style.css, app.js)
├── scripts/test_processing.py     # ejecución sin interfaz
├── data/processed/                # capturas tomadas por los botones
├── build_portable.ps1             # construye una carpeta portátil en Windows
└── requirements.txt
```

La interfaz es HTML/CSS/JS renderizada en una ventana nativa con `pywebview`.
Los botones "Capturar imagen 1" y "Capturar imagen 2" llaman a `Api.capturar`,
que usa `processing/screen_capture.py` para: ocultar la ventana de la app,
esperar 3 segundos a que el programa externo (ELECAV, un visor de imágenes,
etc.) quede en primer plano, capturar el monitor donde está esa ventana y
restaurar la app siempre, incluso si falla la captura. No busca ninguna
ventana por título: captura lo que haya quedado al frente tras ocultarse.

Tras cada captura, `Api.capturar` también detecta la rejilla de la tabla y
cuenta sus filas con `ImageProcessor.detectar_tabla` (sin leer los valores
todavía). "Confirmar y transcribir" llama a `Api.procesar(fila)`, que valida
que ambas capturas tengan la misma cantidad de filas y ejecuta el OCR de los
7 campos requeridos solo sobre la fila elegida ("Última fila" por defecto, o
una fila específica) con `ImageProcessor.transcribir_fila`. El script
independiente (`scripts/test_processing.py`) sigue usando `ImageProcessor.process`,
que aplica la última fila de cada vista sin pasar por la interfaz. El
procesador devuelve `ResultadoProcesado`, que contiene un `Resultado` con
valores de texto, campos pendientes y avisos.

## Uso del operario (carpeta portátil)

La carpeta `dist/LectorResultados` generada por `build_portable.ps1` contiene la
aplicación, Tesseract y sus datos de idioma. Entregue **toda la carpeta** al
operario. El operario abre `LectorResultados.exe` con el reporte (ELECAV u
otro visor) ya abierto y maximizado detrás, pulsa "Capturar imagen 1" (la app
se oculta 3 segundos y captura lo que quedó al frente), luego "Capturar
imagen 2" con la segunda parte del reporte visible, elige la fila a
transcribir (por defecto la última) y por último "Confirmar y transcribir".
El resultado se muestra en la propia ventana y puede exportarse a CSV con el
botón "Descargar CSV". No instala Python ni Tesseract.

Esta carpeta se construye y se verifica en Windows antes de distribuirla. El
archivo ZIP del código fuente aún no es el ejecutable para el operario.

## Construcción en el equipo de desarrollo (Windows)

Instale Python y Tesseract **solo en el equipo donde se construye la aplicación**.
Compruebe que exista `tesseract.exe` y `tessdata/eng.traineddata` dentro de la
carpeta de Tesseract. En PowerShell, desde `lector_tabla`:

```powershell
.\build_portable.ps1 -TesseractDir "C:\Program Files\Tesseract-OCR"
```

El script crea el entorno de Python, instala dependencias y genera
`dist/LectorResultados`. Pruebe el ejecutable con dos capturas reales de la
misma tabla en una máquina Windows sin Python ni Tesseract instalados antes de
entregarlo. Las dependencias binarias de Tesseract deben distribuirse conforme
a sus respectivas licencias.

## Ejecución del código fuente (desarrollo)

Instale Python 3.10 o posterior y Tesseract en el equipo de desarrollo.
En Windows, agregue `tesseract.exe` al PATH;
si solo usará el script puede indicar su ruta mediante `--tesseract-cmd`.

Desde la carpeta `lector_tabla`:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Para procesar sin abrir la ventana:

```bash
python scripts/test_processing.py --image1 ruta/captura1.png --image2 ruta/captura2.png
```

El resultado se imprime como JSON en consola. Una incompatibilidad o una lectura
incierta produce un error y el script termina con código 1.

## Alcance de esta versión

Use dos capturas directas, completas y legibles de la **misma tabla**, una con
las columnas de condiciones del ensayo (encabezado con `Fecha`/`Hora`) y otra
con las columnas de resultados mecánicos (encabezado con `fluencia`/`rotura`).
El detector busca una rejilla recta; omite encabezado y pies de tabla del
conteo de filas.

La selección de fila es **por posición**, no por identificador de ensayo: la
fila 1 es el primer registro de datos debajo del encabezado en cada captura,
y así sucesivamente. La app no valida que ambas capturas correspondan al
mismo registro ni usa `Módulo de Young` ni el número `No` para emparejarlas:
es responsabilidad de quien captura asegurarse de que ambas vistas muestren
los mismos registros y en el mismo orden. Si las dos capturas detectan una
cantidad distinta de filas, la app bloquea la transcripción y pide repetir
una captura.

Solo se transcriben los 7 campos requeridos (esfuerzo máximo, esfuerzo en
fluencia, carga máxima, longitud y diámetro de probeta, temperatura y
humedad) de la fila elegida. Los campos cuyo OCR no supera el umbral se
entregan como `null`; no se inventan valores ni se reintenta con otra fila.
El OCR no corrige ni completa mediciones.
