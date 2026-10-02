param(
    [string]$Manifest = 'data/eval/manifest.jsonl',
    [string]$OutputDirectory = 'data/eval/asr-diagnostic'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$destination = [System.IO.Path]::GetFullPath((Join-Path $PWD $OutputDirectory))
if (Test-Path -LiteralPath $destination) { throw 'Use a new output directory to preserve evidence.' }
New-Item -ItemType Directory -Path (Join-Path $destination 'audio') -Force | Out-Null
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $english = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'en-*' } | Select-Object -First 1
    if (-not $english) { throw 'No Windows English SAPI voice available.' }
    $synth.SelectVoice($english.VoiceInfo.Name)
    $synth.Rate = 1
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $rows = Get-Content -LiteralPath $Manifest -Encoding utf8 | ForEach-Object { $_ | ConvertFrom-Json }
    foreach ($row in $rows) {
        $wave = Join-Path $destination ('audio/' + $row.case_id + '.wav')
        $synth.SetOutputToWaveFile($wave, $format)
        $synth.Speak($row.english_reference)
        $synth.SetOutputToNull()
        $row.audio_kind = 'diagnostic_sapi'
        $row.english_reviewed = $false
        $row.hindi_reviewed = $false
    }
    $rows | ForEach-Object { $_ | ConvertTo-Json -Compress } | Set-Content -LiteralPath (Join-Path $destination 'manifest.jsonl') -Encoding utf8NoBOM
} finally { $synth.Dispose() }
# Pad short diagnostic clips with silence; never truncate long clips or imply human recordings.
$env:ARKE_DIAGNOSTIC_DIR = $destination
@'
import json, os
from pathlib import Path
import numpy as np
import soundfile as sf
root = Path(os.environ['ARKE_DIAGNOSTIC_DIR'])
path = root / 'manifest.jsonl'
rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
for row in rows:
    wave = root / row['audio_path']
    samples, rate = sf.read(wave, dtype='float32')
    if len(samples) < 2 * rate:
        samples = np.pad(samples, (0, 2 * rate - len(samples)))
        sf.write(wave, samples, rate, subtype='PCM_16')
    if len(samples) > 6 * rate:
        raise RuntimeError('Diagnostic clip exceeds 6 seconds; increase explicit SAPI rate and regenerate')
    row['source_duration'] = len(samples) / rate
path.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows), encoding='utf-8')
print('30 local SAPI diagnostic clips generated; human ASR evaluation remains pending')
'@ | & .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw 'Diagnostic clip preparation failed.' }

