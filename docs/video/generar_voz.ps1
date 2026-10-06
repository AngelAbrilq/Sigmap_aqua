Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'es-*' } | Select-Object -First 1
if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }
$s.Rate = 0
$out = Join-Path $PSScriptRoot 'audio'
New-Item -ItemType Directory -Force $out | Out-Null
$lines = Get-Content (Join-Path $PSScriptRoot 'narracion.txt') -Encoding UTF8
$i = 0
foreach ($l in $lines) { if ($l.Trim()) { $i++; $s.SetOutputToWaveFile((Join-Path $out ('escena{0:D2}.wav' -f $i))); $s.Speak($l) } }
$s.SetOutputToNull()
$voces = ($s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name + ' ' + $_.VoiceInfo.Culture.Name }) -join '; '
"usada: $($v.VoiceInfo.Name) | instaladas: $voces" | Out-File (Join-Path $out 'voz.txt') -Encoding UTF8
Write-Host "LISTO $i escenas"
