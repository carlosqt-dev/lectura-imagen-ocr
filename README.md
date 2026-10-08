# Lector de resultados (prototipo)

## Estructura

```text
lector_tabla/
├── main.py                  # inicia la ventana
├── models/result.py         # resultado y avisos
├── processing/image_processor.py  # rejilla, OCR, selección y comparación
├── ui/window.py             # dos selectores de archivos
├── scripts/test_processing.py # ejecución sin interfaz
├── data/processed/          # reservado para una versión futura
├── build_portable.ps1       # construye una carpeta portátil en Windows
└── requirements.txt
```

La ventana selecciona las dos imágenes y entrega sus rutas a `ImageProcessor`.
El script independiente hace la misma llamada sin importar PySide6. El procesador
devuelve `ResultadoProcesado`, que contiene un `Resultado` con valores de texto,
campos pendientes y avisos. No escribe archivos de resultados.

## Uso del operario (carpeta portátil)

La carpeta `dist/LectorResultados` generada por `build_portable.ps1` contiene la
aplicación, Tesseract y sus datos de idioma. Entregue **toda la carpeta** al
operario. El operario abre `LectorResultados.exe` y elige sus dos capturas; no
instala Python ni Tesseract. Se mantiene una consola abierta para mostrar el JSON.

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

## Alcance de esta primera versión

Use dos capturas directas, completas y legibles de la **misma tabla**, tomadas
antes y después del desplazamiento horizontal, sin modificar el orden ni el
número de filas. El detector busca una rejilla recta y un encabezado con
`Módulo de Young`. Omite filas de estadísticas identificadas por su texto o
sin identificador individual, y elige la última fila restante.

La comparación exige que el número de filas coincida. Cada fila debe compartir
el número `No`, o tener un valor único de `Módulo de Young` que coincida en ambas
vistas; el módulo debe coincidir siempre. Si las condiciones no se cumplen, no
se emite registro. Los campos cuyo OCR no supera el umbral se entregan como
`null`; los encabezados no identificables se dejan como aviso. El OCR no corrige
ni completa mediciones.

Las dos imágenes usadas como referencia en la solicitud **no corresponden al
mismo resultado**: la segunda es una fotografía con perspectiva y números de fila
distintos. Se deben tomar dos capturas nuevas del mismo ensayo para probar una
unión real. La perspectiva de fotografías y encabezados muy borrosos están fuera
del alcance del detector inicial. Además, la columna a la derecha de `Esfuerzo
en límite elástico` en la foto no tiene título suficientemente legible, por lo
que queda pendiente de revisión y no recibe nombre inventado.
