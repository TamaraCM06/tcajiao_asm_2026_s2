param(
    [ValidateSet('build', 'flash', 'monitor', 'size')][string]$Accion = 'build',
    [string]$Puerto,
    [string]$RutaSdk = 'C:/Espressif/frameworks/esp-idf-v5.5.5',
    [string]$RutaHerramientas = 'C:/Espressif',
    [string]$PythonSdk = 'C:/Espressif/python_env/idf5.5_py3.11_env/Scripts/python.exe'
)

# Compila una copia aislada ASCII porque IDF resuelve los alias a la ruta con tildes.
$ErrorActionPreference = 'Stop'
if (($Accion -eq 'flash' -or $Accion -eq 'monitor') -and -not $Puerto) {
    throw 'Indica -Puerto COMx para programar o abrir la consola.'
}
$entornoAnterior = @{}
$rutaRegistro = Join-Path $PSScriptRoot 'build/ruta_compilacion.txt'
try {
    foreach ($nombre in @('IDF_PATH', 'IDF_TOOLS_PATH', 'PYTHONUTF8')) {
        $entornoAnterior[$nombre] = [Environment]::GetEnvironmentVariable($nombre, 'Process')
    }
    $env:IDF_PATH = $RutaSdk
    $env:IDF_TOOLS_PATH = $RutaHerramientas
    $env:PYTHONUTF8 = '1'
    $salidaEntorno = & $PythonSdk "$RutaSdk/tools/idf_tools.py" export --format=key-value
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo activar ESP-IDF.' }
    foreach ($linea in $salidaEntorno) {
        if ($linea -match '^([A-Z_]+)=(.*)$') {
            $nombre = $Matches[1]
            $valor = $Matches[2].Replace('%PATH%', $env:PATH)
            if (-not $entornoAnterior.ContainsKey($nombre)) {
                $entornoAnterior[$nombre] = [Environment]::GetEnvironmentVariable($nombre, 'Process')
            }
            [Environment]::SetEnvironmentVariable($nombre, $valor, 'Process')
        }
    }
    if ($Accion -eq 'build') {
        $rutaCopia = Join-Path $env:TEMP ('asm_esp32_' + [guid]::NewGuid().ToString('N'))
        if ($rutaCopia -match '[^\x00-\x7F]|\s') { throw 'TEMP debe ser una ruta ASCII sin espacios para ESP-IDF.' }
        New-Item -ItemType Directory -Path $rutaCopia | Out-Null
        foreach ($nombre in @('components', 'main', 'CMakeLists.txt', 'sdkconfig.defaults', 'partitions.csv')) {
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot $nombre) -Destination $rutaCopia -Recurse
        }
    } else {
        if (-not (Test-Path -LiteralPath $rutaRegistro)) { throw 'Primero ejecuta una compilacion correcta.' }
        $rutaCopia = (Get-Content -LiteralPath $rutaRegistro -Raw).Trim()
        if (-not (Test-Path -LiteralPath (Join-Path $rutaCopia 'build/emisor_esp32.bin'))) {
            throw 'La copia compilada ya no existe. Ejecuta build nuevamente.'
        }
    }
    $argumentosIdf = @('-C', $rutaCopia)
    if ($Puerto) { $argumentosIdf += @('-p', $Puerto) }
    & $PythonSdk "$RutaSdk/tools/idf.py" @argumentosIdf $Accion
    if ($LASTEXITCODE -ne 0) { throw "ESP-IDF termino con error $LASTEXITCODE." }
    if ($Accion -eq 'build') {
        New-Item -ItemType Directory -Force -Path (Split-Path $rutaRegistro) | Out-Null
        Set-Content -LiteralPath $rutaRegistro -Value $rutaCopia -Encoding ASCII
        Write-Output "Firmware compilado en $rutaCopia/build; flash usara esta copia."
    }
} finally {
    foreach ($nombre in $entornoAnterior.Keys) {
        [Environment]::SetEnvironmentVariable($nombre, $entornoAnterior[$nombre], 'Process')
    }
}
