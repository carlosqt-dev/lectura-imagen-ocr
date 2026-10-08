# Se ejecuta EN WINDOWS en el equipo de desarrollo, no en el del operario.
param(
    [string]$TesseractDir = "C:\Program Files\Tesseract-OCR"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$ocrExe = Join-Path $TesseractDir "tesseract.exe"
$engData = Join-Path $TesseractDir "tessdata\eng.traineddata"
if (!(Test-Path $ocrExe) -or !(Test-Path $engData)) {
    throw "En el equipo de desarrollo faltan tesseract.exe o tessdata\eng.traineddata en $TesseractDir"
}

if (!(Test-Path ".venv\Scripts\python.exe")) {
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual." }
}
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python -m pip install -r requirements.txt "pyinstaller>=6,<7"
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias de construcción." }

$argsPy = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
    "--name", "LectorResultados", "--paths", ".",
    "--add-binary", "${ocrExe}:tesseract",
    "--add-data", "$(Join-Path $TesseractDir 'tessdata'):tesseract/tessdata"
)
Get-ChildItem $TesseractDir -Filter "*.dll" -File | ForEach-Object {
    $argsPy += @("--add-binary", "$($_.FullName):tesseract")
}
$argsPy += "main.py"
& $python @argsPy
if ($LASTEXITCODE -ne 0) { throw "Falló la construcción del ejecutable." }

$builtExe = Join-Path $PSScriptRoot "dist\LectorResultados\LectorResultados.exe"
$bundledOcr = Join-Path $PSScriptRoot "dist\LectorResultados\_internal\tesseract\tesseract.exe"
if (!(Test-Path $builtExe) -or !(Test-Path $bundledOcr)) {
    throw "No se encontraron la aplicación y el motor OCR en dist\LectorResultados."
}
Write-Host "Carpeta para entregar al operario: $PSScriptRoot\dist\LectorResultados"
Write-Host "Copie la carpeta completa y abra LectorResultados.exe."
