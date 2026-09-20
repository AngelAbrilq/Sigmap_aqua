<#
.SYNOPSIS
  Levanta todo el entorno de desarrollo y abre la app en el emulador.

.DESCRIPTION
  1. Abre una ventana con Django: migrate + datos de demo + runserver 0.0.0.0:8000.
  2. Arranca el primer emulador Android (AVD) si no hay uno encendido.
  3. Espera a que el emulador termine de iniciar.
  4. flutter run apuntando a http://10.0.2.2:8000 (el PC visto desde el emulador).

  Usuarios de demo (python manage.py preparar_demo):
    instructor@sigmap.com / Instructor2026*
    operario@sigmap.com   / Operario2026*
    aprendiz@sigmap.com   / Aprendiz2026*

.PARAMETER SinDemo
  No recarga los datos de demostración.

.EXAMPLE
  cd mobile
  powershell -ExecutionPolicy Bypass -File .\tool\run_dev.ps1
#>
param([switch]$SinDemo)

$ErrorActionPreference = 'Stop'
$mobile = Split-Path $PSScriptRoot -Parent
$raiz = Split-Path $mobile -Parent

# --- 1. Backend -------------------------------------------------------------
$comandosDjango = @(
    "Set-Location '$raiz'",
    '.\venv\Scripts\Activate.ps1',
    'python manage.py migrate --noinput'
)
if (-not $SinDemo) { $comandosDjango += 'python manage.py preparar_demo' }
$comandosDjango += 'python manage.py runserver 0.0.0.0:8000'

Write-Host '1/4 Iniciando Django en otra ventana...' -ForegroundColor Cyan
Start-Process powershell -ArgumentList @('-NoExit', '-Command', ($comandosDjango -join '; '))

# --- 2. Emulador ------------------------------------------------------------
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
$adb = Join-Path $sdk 'platform-tools\adb.exe'
$emulador = Join-Path $sdk 'emulator\emulator.exe'

if (-not (Test-Path $adb)) { throw "No se encontró adb en $adb. Instala 'Android SDK Platform-Tools' desde Android Studio." }

$encendido = (& $adb devices) -match '^emulator-\d+\s+device'
if (-not $encendido) {
    if (-not (Test-Path $emulador)) { throw "No se encontró el emulador en $emulador." }
    $avds = @(& $emulador -list-avds | Where-Object { $_ -and $_ -notmatch '^INFO' })
    if ($avds.Count -eq 0) {
        throw 'No hay emuladores creados. Android Studio > Device Manager > Create Virtual Device.'
    }
    Write-Host "2/4 Arrancando emulador '$($avds[0])'..." -ForegroundColor Cyan
    Start-Process $emulador -ArgumentList @('-avd', $avds[0])
} else {
    Write-Host '2/4 Ya hay un emulador encendido.' -ForegroundColor Cyan
}

# --- 3. Esperar arranque completo -------------------------------------------
Write-Host '3/4 Esperando a que Android termine de iniciar...' -ForegroundColor Cyan
& $adb wait-for-device
$limite = (Get-Date).AddMinutes(4)
do {
    Start-Sleep -Seconds 3
    $listo = (& $adb shell getprop sys.boot_completed 2>$null) -match '1'
} until ($listo -or (Get-Date) -gt $limite)
if (-not $listo) { throw 'El emulador no terminó de iniciar en 4 minutos.' }

# --- 4. App -----------------------------------------------------------------
Write-Host '4/4 Ejecutando la app (r = hot reload, R = restart, q = salir)...' -ForegroundColor Cyan
Set-Location $mobile
flutter run --dart-define=API_URL=http://10.0.2.2:8000/api/v1/movil
