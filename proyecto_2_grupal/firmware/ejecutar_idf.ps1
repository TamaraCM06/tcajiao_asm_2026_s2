# Ejecuta ESP-IDF en una copia ASCII y conserva la configuracion local del banco.
[CmdletBinding()]
param(
    [ValidateSet('build', 'menuconfig', 'flash', 'monitor', 'size')][string]$Accion = 'build',
    [string]$Puerto,
    [string]$RutaSdk = 'C:/Espressif/frameworks/esp-idf-v5.5.5',
    [string]$PythonSdk = 'C:/Espressif/python_env/idf5.5_py3.11_env/Scripts/python.exe'
)
$ErrorActionPreference = 'Stop'
if (($Accion -eq 'flash' -or $Accion -eq 'monitor') -and -not $Puerto) { throw 'Indica -Puerto COMx.' }
$entornoAnterior = @{}
$rutaRegistro = Join-Path $PSScriptRoot 'build/ruta_compilacion.txt'
try {
    foreach ($nombreVariable in @('IDF_PATH', 'IDF_TOOLS_PATH', 'PYTHONUTF8', 'IDF_VERSION', 'ESP_IDF_VERSION', 'PATH')) {
        $entornoAnterior[$nombreVariable] = [Environment]::GetEnvironmentVariable($nombreVariable, 'Process')
    }
    $env:IDF_PATH = $RutaSdk
    $env:IDF_TOOLS_PATH = 'C:/Espressif'
    $env:PYTHONUTF8 = '1'
    $salidaEntorno = & $PythonSdk "$RutaSdk/tools/idf_tools.py" export --format=key-value
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo activar ESP-IDF.' }
    foreach ($lineaEntorno in $salidaEntorno) {
        if ($lineaEntorno -match '^([A-Z_]+)=(.*)$') {
            $nombreVariable = $Matches[1]
            if (-not $entornoAnterior.ContainsKey($nombreVariable)) {
                $entornoAnterior[$nombreVariable] = [Environment]::GetEnvironmentVariable($nombreVariable, 'Process')
            }
            $valorVariable = $Matches[2].Replace('%PATH%', $env:PATH)
            [Environment]::SetEnvironmentVariable($nombreVariable, $valorVariable, 'Process')
        }
    }
    if ($Accion -eq 'build' -or $Accion -eq 'menuconfig') {
        $rutaCopia = Join-Path $env:TEMP ('asm2_registrador_' + [guid]::NewGuid().ToString('N'))
        if ($rutaCopia -match '[^\x00-\x7F]|\s') { throw 'TEMP debe ser ASCII sin espacios.' }
        New-Item -ItemType Directory -Path $rutaCopia | Out-Null
        foreach ($nombreArchivo in @('src', 'include', 'CMakeLists.txt', 'sdkconfig.defaults')) {
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot $nombreArchivo) -Destination $rutaCopia -Recurse
        }
        if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'sdkconfig')) {
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'sdkconfig') -Destination $rutaCopia
        }
        $revisionFirmware = & git -C $PSScriptRoot describe --always --dirty
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo leer la revision Git.' }
        Set-Content -LiteralPath (Join-Path $rutaCopia 'version.txt') -Value $revisionFirmware -Encoding ASCII
    } else {
        if (-not (Test-Path -LiteralPath $rutaRegistro)) { throw 'Primero ejecuta build.' }
        $rutaCopia = (Get-Content -LiteralPath $rutaRegistro -Raw).Trim()
        if (-not (Test-Path -LiteralPath (Join-Path $rutaCopia 'build/asm2_registrador.bin'))) {
            throw 'No existe la copia compilada; ejecuta build nuevamente.'
        }
    }
    $argumentosIdf = @('-C', $rutaCopia)
    if ($Puerto) { $argumentosIdf += @('-p', $Puerto) }
    & $PythonSdk "$RutaSdk/tools/idf.py" @argumentosIdf $Accion
    if ($LASTEXITCODE -ne 0) { throw "ESP-IDF termino con error $LASTEXITCODE." }
    if ($Accion -eq 'build' -or $Accion -eq 'menuconfig') {
        Copy-Item -LiteralPath (Join-Path $rutaCopia 'sdkconfig') -Destination (Join-Path $PSScriptRoot 'sdkconfig')
    }
    if ($Accion -eq 'build') {
        New-Item -ItemType Directory -Force -Path (Split-Path $rutaRegistro) | Out-Null
        Set-Content -LiteralPath $rutaRegistro -Value $rutaCopia -Encoding ASCII
        Write-Output "Compilacion $revisionFirmware disponible en $rutaCopia/build."
    }
} finally {
    foreach ($nombreVariable in $entornoAnterior.Keys) {
        [Environment]::SetEnvironmentVariable($nombreVariable, $entornoAnterior[$nombreVariable], 'Process')
    }
}
