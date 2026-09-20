<#
.SYNOPSIS
  Genera las carpetas nativas (android/ios) con `flutter create` y deja la
  app lista para ejecutar. Es seguro correrlo varias veces.

.DESCRIPTION
  El código Dart (lib/, test/, pubspec.yaml) ya está en el repo. Este script:
    1. Corre `flutter create .` -> solo crea archivos que NO existen,
       así que no toca lib/, test/ ni pubspec.yaml.
    2. Agrega el permiso INTERNET al manifest principal (sin él, el APK
       release no puede llamar a la API).
    3. Permite HTTP sin TLS solo en debug (Django local en http://).
    4. Cambia el nombre visible de la app a "BioAqua".
    5. Instala dependencias y corre análisis + pruebas.

.EXAMPLE
  cd mobile
  powershell -ExecutionPolicy Bypass -File .\tool\setup.ps1
#>
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

# PowerShell 5.1 escribe UTF-8 con BOM; se usa .NET para evitarlo.
$utf8SinBom = New-Object System.Text.UTF8Encoding $false

function Update-TextFile([string]$Path, [scriptblock]$Transform) {
    $original = [System.IO.File]::ReadAllText((Resolve-Path $Path).Path)
    $updated = & $Transform $original
    if ($updated -ne $original) {
        [System.IO.File]::WriteAllText((Resolve-Path $Path).Path, $updated, $utf8SinBom)
        Write-Host "  actualizado: $Path" -ForegroundColor Green
    }
}

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw 'Flutter no está en el PATH. Instálalo y verifica con "flutter doctor".'
}

Write-Host '1/5 Generando plataformas android e ios...' -ForegroundColor Cyan
flutter create --org co.edu.sena.bioaqua --project-name sigmap_aqua_mobile --platforms android,ios .
if ($LASTEXITCODE -ne 0) { throw 'flutter create falló.' }

Write-Host '2/5 Permiso INTERNET en el manifest principal...' -ForegroundColor Cyan
Update-TextFile 'android/app/src/main/AndroidManifest.xml' {
    param($xml)
    if ($xml -match 'android\.permission\.INTERNET') { return $xml }
    $xml -replace '(<manifest[^>]*>)', "`$1`n    <uses-permission android:name=`"android.permission.INTERNET`"/>"
}

Write-Host '3/5 HTTP local permitido solo en debug...' -ForegroundColor Cyan
Update-TextFile 'android/app/src/debug/AndroidManifest.xml' {
    param($xml)
    if ($xml -match 'usesCleartextTraffic') { return $xml }
    $xml -replace '</manifest>', "    <application android:usesCleartextTraffic=`"true`" />`n</manifest>"
}

Write-Host '4/5 Nombre visible de la app...' -ForegroundColor Cyan
Update-TextFile 'android/app/src/main/AndroidManifest.xml' {
    param($xml)
    $xml -replace 'android:label="[^"]*"', 'android:label="BioAqua"'
}
if (Test-Path 'ios/Runner/Info.plist') {
    Update-TextFile 'ios/Runner/Info.plist' {
        param($plist)
        $plist -replace '(<key>CFBundleDisplayName</key>\s*<string>)[^<]*(</string>)', '${1}BioAqua${2}'
    }
}

Write-Host '5/5 Dependencias, análisis y pruebas...' -ForegroundColor Cyan
flutter pub get
if ($LASTEXITCODE -ne 0) { throw 'flutter pub get falló.' }
flutter analyze
flutter test

Write-Host ''
Write-Host 'Listo. Para ejecutar:' -ForegroundColor Green
Write-Host '  Emulador Android : flutter run'
Write-Host '  Celular físico   : copia dart_defines.example.json a dart_defines.local.json,'
Write-Host '                     pon la IP de tu PC y corre:'
Write-Host '                     flutter run --dart-define-from-file=dart_defines.local.json'
