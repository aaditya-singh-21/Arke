param([switch]$Asr, [switch]$Translation, [switch]$Tts)
$ErrorActionPreference = 'Stop'
$env:UV_CACHE_DIR = Join-Path $PWD '.cache/uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.python'
uv python install 3.11
if ($LASTEXITCODE -ne 0) { throw 'Python provisioning failed.' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    uv venv --python 3.11 .venv
    if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed.' }
}
& ./.venv/Scripts/python.exe -c 'import sys; assert sys.version_info[:2] == (3, 11)'
if ($LASTEXITCODE -ne 0) { throw 'Existing .venv is not runnable Python 3.11; repair its base interpreter before installation.' }
uv pip install --python .venv/Scripts/python.exe -e '.[test,audio]'
if ($LASTEXITCODE -ne 0) { throw 'Foundation installation failed.' }
if ($Asr) {
    uv pip install --python .venv/Scripts/python.exe -e '.[asr]'
    if ($LASTEXITCODE -ne 0) { throw 'ASR installation failed.' }
}
if ($Translation -or $Tts) {
    uv pip install --python .venv/Scripts/python.exe 'torch==2.7.1' --index-url https://download.pytorch.org/whl/cu126
    if ($LASTEXITCODE -ne 0) { throw 'Pinned PyTorch installation failed.' }
}
if ($Translation) {
    uv pip install --python .venv/Scripts/python.exe -e '.[translation]'
    if ($LASTEXITCODE -ne 0) { throw 'Translation dependencies failed.' }
    Write-Host 'Official IndicTransToolkit 1.1.1 is included; its Windows source build requires a working C++ compiler.'
}
if ($Tts) {
    uv pip install --python .venv/Scripts/python.exe -e '.[tts]'
    if ($LASTEXITCODE -ne 0) { throw 'TTS dependencies failed.' }
}
& ./.venv/Scripts/python.exe -m voice_translator doctor --output artifacts/doctor.json
if ($LASTEXITCODE -ne 0) { throw 'Doctor failed.' }

