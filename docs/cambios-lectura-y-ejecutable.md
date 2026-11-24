# Cambios en la lectura OCR y cómo generar el ejecutable

Este documento resume qué se corrigió en la lectura de las capturas de ELECAV,
por qué, y cómo construir y entregar el ejecutable portátil.

## 1. Cómo funciona la lectura (vista general)

```text
Imagen 1 (datos)              Imagen 2 (resultados)
   │                              │  (mismo proceso)
   ▼                              ▼
Escala de grises (OpenCV)
   ▼
Detección de la rejilla: líneas horizontales (filas) y verticales (columnas)
   ▼
Lectura de los encabezados → identifica la vista y la columna de cada campo
   ▼
Validación: vistas distintas, misma cantidad de filas, fila elegida existente
   ▼
Para cada celda requerida de la fila elegida:
   recorte al número → escala a 28/30/32 px → blanco y negro → Tesseract (×3)
   → se acepta el valor si al menos 2 de las 3 lecturas coinciden
   ▼
Unión de campos: 4 de datos (Humedad, Temperatura, Longitud, Diámetro)
               + 3 de resultados (Carga máxima, Esfuerzo máximo, Esfuerzo en fluencia)
   ▼
ResultadoProcesado
```

Casi todo vive en `processing/image_processor.py`.

## 2. Problemas encontrados y cómo se corrigieron

### 2.1 Confusión del 5 con el 9 y Humedad vacía

- **Síntoma:** "Longitud probeta" salía `90` en vez de `50`; "Esfuerzo en
  fluencia" `938,25` en vez de `538,25`; Humedad a veces vacía (`—`).
- **Causa:** cada celda se ampliaba con un factor fijo (3x o 5x). Los dígitos de
  ELECAV miden 15–19 px, así que llegaban a Tesseract con 45–95 px, muy por
  encima de lo que lee bien (~30 px), y con los grises del suavizado de
  Windows en los bordes. Con eso el 5 se parecía al 9.
- **Corrección:** cada número se recorta a su contenido real
  (`_recortar_contenido`), se escala según el alto del propio dígito y se pasa
  a blanco y negro puro con el umbral de Otsu (`_leer`).
- **Resultado:** de 166/210 a 210/210 valores correctos en tres juegos de
  capturas.

### 2.2 Dependencia de la resolución de pantalla

- **Síntoma:** "Se detectaron 18 columnas" en una captura cuyo borde de
  ventana medía justo 20 px.
- **Causa:** los umbrales (alto de fila, franjas sobrantes, márgenes) eran
  números fijos de píxeles calibrados en una sola pantalla.
- **Corrección:** se calculan a partir de la propia captura (mediana de alto de
  fila, fracción del tamaño del dígito, etc.), así funcionan con cualquier
  resolución o escalado de Windows.

### 2.3 Capturas con columnas anchas o cortadas (imágenes "PT" del cliente)

- **Síntoma:** los pares 1, 2 y 3 fallaban al detectar la tabla ("15
  columnas", "no se detectó el borde de la columna No", "columna 8 de 133 px").
- **Causa:** ELECAV ensancha columnas según su texto ("ANALISTA", "ID
  cliente"). Entonces no entran las 17 columnas en la ventana y, a veces, la
  imagen empieza justo en el borde de la tabla y no se ve la línea izquierda.
  El código ubicaba cada dato por **posición fija** y exigía 17 columnas de
  ancho parecido.
- **Corrección:** las columnas se identifican por su **encabezado**
  (`_ubicar_campos`, con las claves de `CLAVES_DATOS` y `CLAVES_RESULTADOS`).
  - Solo se usan palabras de las primeras líneas del encabezado, porque la
    tercera suele quedar cortada y Tesseract la lee como basura.
  - Los encabezados reconocidos sirven de **anclas**. Como ELECAV siempre
    muestra las columnas en el mismo orden, las anclas indican la posición de
    las demás (por ejemplo, "Esfuerzo en fluencia" queda entre "Carga en
    fluencia" y "Esfuerzo en límite").
  - **Seguridad:** si una ancla no cuadra con las demás (falta o sobra una
    línea), o una columna requerida no se ve o está cortada, el programa frena
    con un mensaje claro en vez de leer la columna equivocada.

### 2.4 Elementos que se colaban en la celda

- **Síntoma:** comas perdidas o convertidas en punto (`49343`, `459.61`) en la
  primera y la última fila.
- **Causa:** la línea punteada de la fila seleccionada en ELECAV y el borde de
  la barra de desplazamiento bajo la última fila entraban en el recorte,
  inflaban el "alto del dígito" y el número se escalaba de menos.
- **Corrección (`_recortar_contenido`):** se borran las filas o columnas de
  píxeles que cruzan casi toda la celda (líneas, franjas) y los puntos sueltos
  que tocan el borde de arriba o de abajo. Los puntos del medio se conservan
  porque pueden ser partes de la coma.

### 2.5 Lectura inestable a un tamaño puntual

- **Síntoma:** un `7` leído como `1` (`797,57` → `197,57`) en una celda limpia.
- **Causa:** Tesseract, a un alto puntual, confunde un dígito que a los altos
  vecinos lee bien.
- **Corrección:** cada valor se lee a 28, 30 y 32 px (`ALTOS_DIGITO`) y se
  exige que al menos 2 lecturas coincidan; si no, el campo queda pendiente
  para revisión. Ningún alto suelto pasaba de 304/305; votando, 305/305.

### 2.6 Problemas del ejecutable (solo aparecían empaquetado)

| Problema | Corrección | Dónde |
|---|---|---|
| Tesseract no encontraba el idioma dentro del `.exe` (rutas con comillas) | Se llama a `tesseract.exe` directamente con `subprocess`; se dejó de usar `pytesseract` | `_ejecutar_tesseract` |
| Fallaba si la carpeta tenía tildes o "ñ" (`C:\Users\José\...`) | Se lanza Tesseract desde su carpeta con `TESSDATA_PREFIX=tessdata` relativo | `ImageProcessor.__init__` |
| Un `tesseract.exe` colgado bloqueaba la app | Timeout de 15 s; el proceso se mata al vencer | `TIMEOUT_OCR_S` |
| La interfaz quedaba bloqueada ante un error inesperado (p. ej. CSV abierto en Excel) | Toda llamada a Python pasa por `llamarApi`, que muestra el error y desbloquea | `ui/web/app.js` |
| "Descargar Excel" fallaba: la plantilla no se empaquetaba | Se incluye la plantilla `.xlsm` en el build | `build_portable.ps1` |
| Las capturas se guardaban dentro de `_internal` | Van a `capturas\` junto al `.exe` | `ui/api.py` |
| Ventana negra de consola junto a la app | Build con `--windowed` | `build_portable.ps1` |
| "Failed to resolve Python.Runtime.Loader.Initialize" al cliente | Archivo `LectorResultados.exe.config` con `loadFromRemoteSources`; Windows bloqueaba las DLL de .NET por venir de un zip descargado | `build_portable.ps1` |
| El build no instalaba (`requirements.txt` pedía Pillow 10, sin soporte para Python 3.14) | Versiones alineadas con las probadas | `requirements.txt` |

Además se agregó `--autoprueba` a `main.py` para probar el OCR del `.exe` sin
abrir la ventana ni tener ELECAV (ver sección 4).

## 3. Validación realizada

| Conjunto | Resultado |
|---|---|
| `5.jpeg` + `6.jpeg` (filas 2343–2352) | 70/70 |
| `3.jpeg` + `4.jpeg` (filas 2376–2385) | 70/70 |
| Capturas del cliente `1 PT1/PT2`, `3 PT1`, `4 PT1` (valores visibles) | 165/165 |
| Las 66 filas de los 6 pares PT: formato y coherencia física | 0 anomalías en 462 valores |

La coherencia física usa que **Esfuerzo máximo = Carga máxima ÷ (π · Diámetro² / 4)**:
en ensayos reales se cumple con un error de 0,01% como mucho, y los errores de
lectura la rompen entre 11% y 9900%.

Tiempos aproximados: detectar la tabla ~1,8 s por captura; transcribir una
fila ~2 s.

## 4. Cómo crear el ejecutable

### 4.1 Requisitos (solo en el equipo donde se construye)

- Windows 10/11 de 64 bits.
- Python 3.14 y el entorno virtual del proyecto en `.venv` (el script lo crea
  si no existe).
- Tesseract OCR instalado en `C:\Program Files\Tesseract-OCR`, con
  `tessdata\eng.traineddata`. Versión usada: 5.5.3 (UB Mannheim).
- La plantilla `F-LA-08-01 ... (Datos diligenciados).xlsm` en la raíz del
  proyecto.
- Conexión a internet la primera vez (instala PyInstaller).

### 4.2 Construir

Desde PowerShell, en la carpeta del proyecto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_portable.ps1
```

Si Tesseract está en otra ruta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_portable.ps1 -TesseractDir "D:\otra\ruta\Tesseract-OCR"
```

El script:

1. Comprueba que existan `tesseract.exe`, `eng.traineddata` y la plantilla.
2. Instala las dependencias y PyInstaller en `.venv`.
3. Empaqueta con PyInstaller (`--onedir --windowed`): Python, dependencias,
   Tesseract con sus DLL y `tessdata`, la interfaz `ui/web` y la plantilla.
4. Escribe `LectorResultados.exe.config` junto al `.exe`.
5. Verifica que estén los archivos clave y, si falta alguno, termina con error.

Resultado: `dist\LectorResultados\`. Tarda 1–2 minutos.

### 4.3 Probar antes de entregar

```powershell
cd dist\LectorResultados
.\LectorResultados.exe --autoprueba "..\..\5.jpeg" "..\..\6.jpeg" resultado.json
Get-Content resultado.json
```

`resultado.json` debe traer los 7 valores de la última fila (para ese par:
Humedad 48, Longitud 50, Carga máxima 90,99). Después abrir
`LectorResultados.exe` con doble clic y comprobar que aparece la ventana.

### 4.4 Empaquetar y entregar

```powershell
Compress-Archive -Path .\dist\LectorResultados -DestinationPath .\dist\LectorResultados.zip -Force
```

Comprimir la carpeta `LectorResultados` (no `dist`), así al extraer queda una
sola carpeta. El zip pesa ~145 MB: enviarlo por Drive, OneDrive o WeTransfer.

Instrucciones para el cliente:

1. Extraer el zip en el Escritorio o en Documentos (no en `C:\Program Files`,
   porque la app guarda las capturas en `capturas\` junto al `.exe`).
2. Abrir `LectorResultados.exe`.
3. Si aparece "Windows protegió su PC" (el `.exe` no está firmado): **Más
   información → Ejecutar de todas formas**. Es una sola vez.

### 4.5 Problemas frecuentes

| Síntoma | Solución |
|---|---|
| PowerShell no deja ejecutar el script | Usar `-ExecutionPolicy Bypass` como en 4.2 |
| Falla `pip install` compilando un paquete | Revisar que `requirements.txt` tenga versiones con soporte para la versión de Python del `.venv` |
| Al cliente le aparece "Unhandled exception… Python.Runtime" | Verificar que llegó `LectorResultados.exe.config`; si no, en PowerShell dentro de la carpeta: `Get-ChildItem -Recurse \| Unblock-File` |
| La ventana abre en blanco | Falta el runtime de Microsoft Edge WebView2 (viene en Windows 11 y en Windows 10 actualizado) |
| "No se pudo ejecutar Tesseract" | Falta `_internal\tesseract\` en la carpeta entregada: volver a copiar la carpeta completa |

## 5. Limitaciones conocidas

- Las columnas requeridas tienen que verse completas en la captura (si
  quedan cortadas, la app lo avisa).
- La fila se elige por posición, no por número de ensayo: la app no verifica
  que las dos capturas sean del mismo registro.
- `processing/validacion.py` (revisión de casillas vacías y valores atípicos)
  está escrito pero **no conectado**; tampoco se usa el campo `alertas` de
  `models/result.py`.
- Unos 60–70 MB del ejecutable son DLL de Tesseract duplicadas por
  PyInstaller; se puede reducir si el tamaño importa.
- Las imágenes de prueba (`*.jpeg`, `* PT1.png`, `* PT2.png`) y los scripts de
  validación no forman parte del repositorio.
