<#
.SYNOPSIS
  Verifica backend y app de una vez y guarda todo en mobile\logs\verificacion.log.

.DESCRIPTION
  1. flutter pub get
  2. flutter analyze
  3. flutter test
  4. Pruebas de la API móvil en Django (tests.test_api_movil). Requiere MySQL
     encendido en Laragon.
  Al final imprime un resumen OK/FALLÓ por paso. El log completo sirve para
  compartirlo o revisarlo sin copiar la terminal.

.EXAMPLE
  cd mobile
  powershell -ExecutionPolicy Bypass -File .\tool\verificar.ps1
#>
$ErrorActionPreference = 'Continue'
$mobile = Split-Path $PSScriptRoot -Parent
$raiz = Split-Path $mobile -Parent
$logs = Join-Path $mobile 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$log = Join-Path $logs 'verificacion.log'
"=== Verificación $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File $log -Encoding utf8

$resumen = [ordered]@{}

function Invoke-Paso([string]$Nombre, [string]$Carpeta, [scriptblock]$Comando) {
    Write-Host "`n>>> $Nombre" -ForegroundColor Cyan
    "`n>>> $Nombre" | Out-File $log -Append -Encoding utf8
    Push-Location $Carpeta
    try {
        $salida = & $Comando 2>&1
        $codigo = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    # Tee-Object de PowerShell 5 escribe UTF-16: se agrega línea a línea en UTF-8.
    $salida | ForEach-Object {
        $linea = "$_"
        Add-Content -Path $log -Value $linea -Encoding utf8
        $linea
    } | Out-Host
    $script:resumen[$Nombre] = if ($codigo -eq 0) { 'OK' } else { "FALLÓ (código $codigo)" }
}

Invoke-Paso 'flutter pub get' $mobile { flutter pub get }
Invoke-Paso 'flutter analyze' $mobile { flutter analyze }
Invoke-Paso 'flutter test' $mobile { flutter test }

$python = Join-Path $raiz 'venv\Scripts\python.exe'
function Test-MySql {
    $cliente = New-Object System.Net.Sockets.TcpClient
    try { $cliente.ConnectAsync('127.0.0.1', 3306).Wait(1500) -and $cliente.Connected }
    catch { $false }
    finally { $cliente.Dispose() }
}

if (-not (Test-MySql)) {
    Write-Host "`n>>> django test_api_movil" -ForegroundColor Cyan
    Write-Host 'MySQL no responde en 127.0.0.1:3306. Abre Laragon y pulsa "Iniciar todo".' -ForegroundColor Yellow
    $resumen['django test_api_movil'] = 'OMITIDO (MySQL apagado: inicia Laragon)'
} elseif (Test-Path $python) {
    Invoke-Paso 'django test_api_movil' $raiz { & $python manage.py test tests.test_api_movil --noinput }
} else {
    $resumen['django test_api_movil'] = 'OMITIDO (no existe venv\Scripts\python.exe)'
}

Write-Host "`n=== Resumen ===" -ForegroundColor Cyan
"`n=== Resumen ===" | Out-File $log -Append -Encoding utf8
foreach ($paso in $resumen.Keys) {
    $linea = '{0,-24} {1}' -f $paso, $resumen[$paso]
    $color = if ($resumen[$paso] -eq 'OK') { 'Green' } else { 'Red' }
    Write-Host $linea -ForegroundColor $color
    $linea | Out-File $log -Append -Encoding utf8
}
Write-Host "`nLog completo: $log"
