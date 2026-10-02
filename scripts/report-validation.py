"""Summarize only existing local evidence; never generate quality/listening scores."""
from pathlib import Path
import json
import argparse
import re
from voice_translator.benchmark import render_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('docs/VALIDATION.md'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    lines = ['# V1 validation evidence', '',
        'Status: V1 application and evaluation tooling implemented. Acceptance remains pending human reference/listening review, a 30-turn microphone session, disconnected real flows, and the documented memory margin.', '',
        'Evidence collected on 2026-10-03. No timing in this report is an estimate. Diagnostic speech is local Windows SAPI synthesis; Hindi reference text is authored draft text awaiting bilingual review. Diagnostic category tags are intended coverage, not evidence of actual accents or noise. These runs do not establish population accuracy or human intelligibility.', '',
        '## Target environment', '']
    doctor_path = root/'artifacts/doctor-final.json'
    if doctor_path.exists():
        doctor = json.loads(doctor_path.read_text(encoding='utf-8'))
        lines.extend([f"- CPU: {doctor['cpu']}; {doctor['logical_cpus']} logical CPUs.",
            f"- OS: {doctor['os']}; Python: {doctor['python'].splitlines()[0]}.",
            f"- System RAM: {doctor['ram']['total']/1024**3:.3f} GiB; snapshot available: {doctor['ram']['available']/1024**3:.3f} GiB."])
        for gpu in doctor['gpu']['devices']:
            lines.append(f"- GPU: {gpu['name']}; dedicated memory {gpu['total_bytes']/1024**3:.3f} GiB; driver {gpu['driver']}.")
        lines.append('- Exact installed package versions: `requirements/windows-tested.txt`. PyTorch 2.7.1+cu126 reported CUDA available; official IndicProcessor 1.1.1 built and imported on Windows.')
    lines.extend(['', 'Background applications were not stopped and power mode was not controlled. RAM headroom was already marginal and varied during downloads/imports. An earlier CPU ASR probe briefly overlapped exploratory GPU loading and is retained at `artifacts/asr-cpu-int8-float32`; the isolated CPU repeat below supersedes it for comparison. All listed real configurations run in separate fresh processes with no concurrent real-provider inference. These results are limited to the current desktop workload. None is a passed combined residency gate.', '',
        '## Observed benchmark results', '',
        'Each completed configuration used 30 cases, 3 warm-up calls, and 3 measured passes (90 observations), plus a separately recorded first call. Percentiles use linear interpolation at `(n-1)*q`, excluding unsuccessful observations while reporting their count. Units are seconds/GiB.', '',
        '| Diagnostic configuration | Successful / scheduled | Warm p50 / p95 | Cold load / launch-to-ready | Peak RSS / total VRAM | Minimum available RAM |',
        '|---|---:|---:|---:|---:|---:|'])
    experiments = [
        ('Fake file pipeline', 'fake-pipeline', 'processing'),
        ('ASR CPU int8_float32 (isolated repeat)', 'asr-cpu-int8-isolated', 'asr'),
        ('ASR GPU FP16', 'asr-gpu-fp16-isolated', 'asr'),
        ('ASR GPU INT8/FP16', 'asr-gpu-int8-isolated', 'asr'),
        ('Hindi TTS CPU FP32', 'tts-cpu-diagnostic', 'tts'),
        ('Translation CPU FP32', 'translation-cpu-diagnostic', 'translation'),
        ('Translation GPU FP16', 'translation-gpu-diagnostic', 'translation'),
        ('File ASR GPU / translation CPU / TTS CPU', 'pipeline-initial-diagnostic', 'processing'),
        ('File ASR GPU / translation GPU / TTS CPU', 'pipeline-gpu-translation-diagnostic', 'processing'),
    ]
    details = []
    def fmt(value, unit=1):
        return 'unmeasured' if value is None else f'{value/unit:.3f}'
    for name, directory, metric in experiments:
        report = root/'artifacts'/directory/'summary.json'
        if not report.exists():
            lines.append(f'| {name} | pending | — | — | — | — |')
            continue
        result = json.loads(report.read_text(encoding='utf-8'))
        report.with_name('summary.md').write_text(render_summary(result), encoding='utf-8')
        measured, memory = result['measured'], result['memory']
        timing = measured['timings_seconds'].get(metric, {})
        lines.append(f"| {name} | {measured['successful']} / {measured['attempted']} | {fmt(timing.get('p50'))} / {fmt(timing.get('p95'))} | {fmt(result.get('cold_load_seconds'))} / {fmt(result.get('cold_startup_seconds'))} | {fmt(memory.get('peak_rss_bytes'),1024**3)} / {fmt(memory.get('peak_total_dedicated_vram_bytes'),1024**3)} | {fmt(memory.get('minimum_available_ram_bytes'),1024**3)} |")
        details.extend([f"### {name}", '', f"- Local evidence: `artifacts/{directory}/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `{result['run_id']}`.",
            f"- Outcomes: {measured['outcomes']}; error codes: {measured['failure_codes']}; fatal error: {result.get('fatal_error')}.",
            f"- Memory gate: **{memory['memory_gate']}**. Sample interval p50/p95: {memory['actual_interval_seconds'].get('p50')} / {memory['actual_interval_seconds'].get('p95')} s. Nominal interval: {memory['requested_interval_seconds']} s."])
        if measured.get('wer') is not None:
            details.append(f"- Diagnostic WER: {measured['wer']:.3%}; not a human clean/noisy evaluation result.")
        for key in ('asr_rtf', 'tts_rtf'):
            if measured[key]['count']:
                details.append(f"- {key} p50/p95: {fmt(measured[key]['p50'])} / {fmt(measured[key]['p95'])}.")
        details.append('')
    lines.extend(['', 'File processing timings end at complete audio readiness. They exclude human speech-end/release lag and actual audible onset. They cannot pass the microphone response gate. Fake timing refers to a test tone and is not model latency. RSS includes resident native allocations; the reports additionally record process private/VMS memory where available. GPU measurements are device-wide and include background use; sampled peaks can miss short allocations.', '',
        '## Verification and remaining gates', '',
        '- Deterministic tests cover contracts, configuration, Unicode console output, silence/empty input, bounds, resampling, cancellation, cleanup, offline sockets, provisioning integrity, lazy ASR consumption, generation termination, benchmark counts/privacy, and review evidence binding.',
        '- Ordinary tests never download/load real models. Provisioned-model tests require `ARKE_MODEL_CHECKS=1`; final test evidence is listed below. Each real stage is checked in a fresh process with cached assets.',
        '- Real adapters use local checksummed assets and a Python socket/DNS guard. This is not proof of physical network disconnection; repeat real file and microphone flows while disconnected for acceptance.',
        '- PTT hardware listing succeeded. The tool execution shell does not supply Windows console key-release events; `listen` fails with an actionable message. Real warm sessions additionally enforce the sampled resident-memory margins before capture. A human must establish sufficient memory headroom, run a focused Windows console, use headphones, and complete the 30-turn session.',
        '- Bilingual English/Hindi reference approval, meaning adequacy, critical-detail review, Hindi listening scores, a recorded demo, true acoustic onset, and manual release lag remain pending. No subjective scores were fabricated.',
        '- Provisional gates are unchanged: clean WER ≤20%; ≥27/30 meaning and intelligibility scores ≥4/5; total dedicated VRAM ≤3.5 GiB; available RAM ≥1 GiB; no crashes/OOM across 30 microphone turns. Speech-end-to-audible targets remain p50 ≤3 s/p95 ≤5 s.', '',
        '## Setup failures and resolutions', '',
        '- Sandboxed dependency/model networking failed initially; explicit setup downloads were performed with approved network access. Python/cache/environment and weights remain in ignored local directories.',
        '- CTranslate2 initially failed with missing `pkg_resources`; setuptools 75.8.2 fixes that compatibility issue. CPU generic INT8 resolved to INT8/FP32 and was rejected; the diagnostic configuration now requests the actual supported precision.',
        '- Windows redirected output initially could not encode Hindi; CLI streams now use UTF-8 and a subprocess regression check passes.',
        '- Initial IndicTrans2 setup was denied. The user accepted repository access conditions; cached login is used without copying credentials to project files. Local model/module caches no longer hide that login.',
        '- IndicTrans2 setup now selects safetensors rather than downloading duplicate binary weights and explicitly provisions both SentencePiece model.SRC/model.TGT files. Custom tokenizer/config/model source was inspected at the pinned revision before enabling trust_remote_code; hashes are verified on load.',
        '- The main environment temporarily pointed to an inaccessible Windows Store Python launcher. Its configuration was repaired to use project-local Python 3.11.15 while retaining installed packages.', '',
        '## Model revisions', ''])
    for stage in ('asr','translation','tts'):
        receipt = root/'models'/stage/'provisioned.json'
        if receipt.exists():
            data=json.loads(receipt.read_text(encoding='utf-8'))
            lines.append(f"- {stage}: `{data['model_id']}` at `{data['revision']}`; checksums are in its ignored provisioning receipt.")
    lines.extend(['', '## Scope and documented deviations', '',
        'Implementation remains English → Hindi, batch size one, serial local inference, bounded CLI/file/PTT operation, stock Hindi voice, and no cloud fallback. Optional VAD is omitted. No Rust, service/database/account infrastructure, meeting integration, virtual audio devices, cloning, or V2 behavior was added.', '',
        'The authorized plan permits finishing code and diagnostic composition while unavailable human evaluation is scaffolded. This does not waive milestone acceptance evidence. Providers and placements remain candidates until quality, offline, stability, and combined memory gates pass. Any exploratory GPU translation configuration is explicit and documented, not an automatic fallback.', '', *details])
    lines.extend(['## Final command checks', ''])
    for filename, command in (
        ('unit-tests-final.txt', '.venv/Scripts/python.exe -m pytest -q'),
        ('model-check-asr.txt', 'ARKE_MODEL_CHECKS=1 .venv/Scripts/python.exe -m pytest -q tests/integration/test_provisioned_models.py -k asr'),
        ('model-check-translation.txt', 'ARKE_MODEL_CHECKS=1 .venv/Scripts/python.exe -m pytest -q tests/integration/test_provisioned_models.py -k translation'),
        ('model-check-tts.txt', 'ARKE_MODEL_CHECKS=1 .venv/Scripts/python.exe -m pytest -q tests/integration/test_provisioned_models.py -k tts')):
        log = root/'artifacts'/filename
        if log.exists():
            outcomes = [line.strip() for line in log.read_text(encoding='utf-8').splitlines()
                        if re.search(r'\d+ (passed|failed|error)', line)]
            lines.append(f"- `{command}`: {'; '.join(outcomes) or 'Inspect local log; result pending'}. Evidence: `artifacts/{filename}`.")
    file_check = root/'artifacts/file-real-result.json'
    if file_check.exists():
        result = json.loads(file_check.read_text(encoding='utf-8-sig'))
        lines.append(f"- Real `translate-file --config configs/v1.toml --play` completed with status `{result['status']}`, first-call processing {result['timings']['processing']:.3f} s, output duration {result['output_duration']:.3f} s. This single cold-first call is separate from warmed benchmark percentiles. Hindi WAV: `artifacts/example-hi.wav`; structured result: `artifacts/file-real-result.json`.")
    playback_check = root/'artifacts/file-playback.json'
    if playback_check.exists():
        playback = json.loads(playback_check.read_text(encoding='utf-8'))
        lines.append(f"- Real PortAudio playback completed through the default JLab headphones at {playback['device_sample_rate']} Hz; audio-ready to scheduled-DAC onset proxy {playback['playback_delay_proxy_seconds']:.3f} s. No output resampling was required. Evidence: `artifacts/file-playback.json`. Actual Bluetooth/acoustic onset and human listening quality remain unmeasured.")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()

