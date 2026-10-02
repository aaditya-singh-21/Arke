# Launches exactly one benchmark child process; no resident Python parent.
param(
    [Parameter(Mandatory=$true)][ValidateSet('asr','translation','tts','pipeline')][string]$Stage,
    [string]$Config = 'configs/v1.toml',
    [string]$Manifest = 'data/eval/manifest.jsonl',
    [Parameter(Mandatory=$true)][string]$Output,
    [switch]$AllowUnreviewed,
    [switch]$RetainContent,
    [string]$BaselineNote = 'unspecified'
)
$ErrorActionPreference = 'Stop'
# Windows Python perf_counter uses QueryPerformanceCounter, as does .NET Stopwatch.
$env:ARKE_BENCHMARK_LAUNCH_CLOCK = ([System.Diagnostics.Stopwatch]::GetTimestamp() / [double][System.Diagnostics.Stopwatch]::Frequency).ToString('R', [System.Globalization.CultureInfo]::InvariantCulture)
$arguments = @('-m','voice_translator','benchmark','--stage',$Stage,'--config',$Config,'--manifest',$Manifest,'--output',$Output,'--baseline-note',$BaselineNote)
if ($AllowUnreviewed) { $arguments += '--allow-unreviewed' }
if ($RetainContent) { $arguments += '--retain-content' }
try {
    & ./.venv/Scripts/python.exe @arguments
    $benchmarkExit = $LASTEXITCODE
} finally { Remove-Item Env:ARKE_BENCHMARK_LAUNCH_CLOCK -ErrorAction SilentlyContinue }
exit $benchmarkExit

