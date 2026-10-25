# processor_file

Escribe los 7 campos que transcribe el OCR (`ImageProcessor.transcribir_fila`) dentro de la
plantilla real de laboratorio (`F-LA-08-01 INFORME DE RESULTADOS TRACCIÓN PARA PROBETAS
ESTANDAR (Datos diligenciados).xlsx`, en la raíz del proyecto), sin tocar ninguna otra celda
del formato: el resto lo sigue diligenciando el operario a mano.

> Nota: el archivo en el repo tiene extensión `.xlsx`, no `.xlsm` como decía el enunciado
> original. Igual contiene un proyecto VBA interno (`load_workbook(..., keep_vba=True)` lo
> confirma), así que `escribir_resultado` lo abre con `keep_vba=True` para no perderlo, sea
> cual sea la extensión del archivo que termine usando el laboratorio.

## Archivos

- `mapeo_celdas.py`: diccionario `{clave_interna: celda}` en la hoja `DATOS PRIMARIOS`, más un
  diccionario de validación de encabezados. Es el único archivo que hay que tocar si cambia la
  plantilla.
- `excel_writer.py`: `escribir_resultado(resultado, ruta_plantilla, ruta_salida) -> Path`. Carga
  la plantilla, valida los encabezados, escribe los 7 valores y guarda una copia.
- `_test_mapeo.py`: `python -m processor_file._test_mapeo` escribe un `Resultado` de ejemplo en
  `data/processed/_test_mapeo_salida.xlsx` para revisar el mapeo sin pasar por el OCR ni por la
  interfaz.

## Mapeo encontrado (hoja `DATOS PRIMARIOS`)

| Clave interna (`Resultado.como_dict()`) | Etiqueta en la plantilla | Celda |
|---|---|---|
| Esfuerzo máximo (MPa) | Esfuerzo máximo a tracción | `D19` |
| Esfuerzo en fluencia (MPa) | Esfuerzo en el límite de fluencia | `E19` |
| Carga máxima (kN) | Fuerza máxima | `F19` |
| Diámetro probeta (mm) | Diámetro inicial | `G19` |
| Longitud probeta (mm) | Longitud inicial | `I19` |
| Temperatura (°C) | Temperatura ambiente °C | `G31` |
| Humedad | Humedad relativa % | `L31` |

Las unidades coinciden exactamente entre el OCR y la plantilla (kN, mm, mm, °C, %): no se hace
ninguna conversión.

### Por qué la fila 19 y no el promedio (fila 22)

La plantilla soporta hasta 3 réplicas para diámetro/longitud (filas 19-21) con un promedio en
la fila 22 (fórmula `AVERAGE`, no se debe sobrescribir). El OCR de este proyecto transcribe una
sola lectura por ensayo, así que se escribe únicamente en la fila 19 (la misma celda que usan
hoy los datos de ejemplo de la plantilla). Si en el futuro el flujo capturara 3 réplicas por
campo, habría que extender el mapeo a `G20/G21`, `I20/I21`, etc.

### Riesgo conocido: encabezados dinámicos

Las celdas de la fila 17 (`D17`, `E17`, `F17`, `G17`, `I17`, ...) no son texto fijo: son
fórmulas `VLOOKUP` contra la tabla `VARIABLESPROBETA`, según el tipo de probeta (`K14`) y el
material (`K15`) elegidos en el formato. El mapeo de arriba se extrajo con `K14="Probeta
redonda"` y `K15="Ferroso"`. Si el operario cambia esas celdas antes de exportar, el significado
de las columnas D..L puede correrse.

Por eso `escribir_resultado` abre la plantilla una segunda vez con `data_only=True` sólo para
leer el valor calculado de esos encabezados y lo compara contra el texto esperado
(`VALIDACION_ENCABEZADOS` en `mapeo_celdas.py`). Si no coincide, registra un `warning` pero
**no detiene el guardado** — el requisito pedía no lanzar excepciones por campos problemáticos.
Revise los logs cuando aparezcan.

## Cómo regenerar el mapeo si cambia la plantilla

1. Abra la plantilla nueva con openpyxl (`openpyxl.load_workbook(ruta, data_only=False)`) y
   recorra `ws.iter_rows()` buscando las 7 etiquetas (ver el bloque `labels` que se usó para
   generar este mapeo, en el historial del proyecto, o simplemente abra el archivo en Excel y
   anote a mano fila/columna).
2. Para los encabezados dinámicos (fila 17 en la plantilla actual), abra la plantilla otra vez
   con `data_only=True` para leer el texto ya calculado, no la fórmula.
3. Actualice `MAPEO_CELDAS` y `VALIDACION_ENCABEZADOS` en `mapeo_celdas.py`.
4. Corra `python -m processor_file._test_mapeo` y abra el `.xlsx` de salida para confirmar que
   cada valor cayó donde corresponde.

## Conexión con `ui/api.py`

`Api.exportar_xlsm()` sigue el mismo patrón que `Api.exportar_csv()`: valida que exista
`self._last_result`, abre `self._window.create_file_dialog(webview.SAVE_DIALOG, ...)` para
elegir dónde guardar, y llama a `escribir_resultado(self._last_result, PLANTILLA_XLSX, ruta)`.
Devuelve `{"ok": True, "path": str(ruta)}` o `{"ok": False, "error": "..."}`, igual que el resto
de los métodos de `Api`.
