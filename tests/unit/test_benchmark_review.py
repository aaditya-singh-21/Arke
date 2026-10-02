from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import pytest
from voice_translator.benchmark import run_benchmark
from voice_translator.config import load_config
from voice_translator.evaluation import init_evaluation, read_jsonl, score_review
from voice_translator.errors import InvalidInput

ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_counts_phases_separates_edges_and_privacy(tmp_path):
    manifest = tmp_path / 'eval' / 'manifest.jsonl'
    init_evaluation(manifest, synthetic=True)
    config = load_config(ROOT / 'configs/fake.toml')
    args = SimpleNamespace(manifest=manifest, stage='pipeline', allow_unreviewed=True,
                           output=tmp_path/'output', retain_content=False, baseline_note='test')
    summary = run_benchmark(config, args)
    records = read_jsonl(args.output/'records.jsonl')
    assert len(records) == 94
    assert sum(x['phase'] == 'warmup' for x in records) == 3
    assert summary['measured']['successful'] == 90 and summary['distinct_case_count'] == 30
    assert len(read_jsonl(args.output/'behavior.jsonl')) == 4
    assert not any('english' in x or 'hindi' in x for x in records)
    assert summary['acceptance_status'] == 'diagnostic_only'
    with pytest.raises(InvalidInput):
        run_benchmark(config, args)


def test_scores_cannot_pass_with_fake_evidence(tmp_path):
    manifest = tmp_path/'manifest.jsonl'
    init_evaluation(manifest)
    cases = read_jsonl(manifest)
    for case in cases:
        case.update(english_reviewed=True, hindi_reviewed=True, audio_kind='human_recording')
    manifest.write_text(''.join(json.dumps(x) + '\n' for x in cases), encoding='utf-8')
    reviews = read_jsonl(tmp_path/'review-template.jsonl')
    for row in reviews:
        row.update(reviewer='Fixture reviewer declaration', meaning_score=5, tts_intelligibility_score=5,
                   critical_details_reviewed=True, translation_run_id='translation-id', tts_run_id='tts-id')
    review = tmp_path/'review.jsonl'
    review.write_text(''.join(json.dumps(x) + '\n' for x in reviews), encoding='utf-8')
    reports = []
    for stage in ('translation', 'tts'):
        output = tmp_path/stage
        output.mkdir()
        run_id = stage+'-id'
        (output/'metadata.json').write_text(json.dumps({'stage':stage,'run_id':run_id,
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}))
        path = output/'summary.json'
        path.write_text(json.dumps({'run_id':run_id,'fake':True,'diagnostic_unreviewed':False,
            'measured':{'successful':90},'distinct_case_count':30}))
        reports.append(path)
    report = score_review(manifest, review, *reports)
    assert report['status'] == 'human_review_pending'
    assert report['meaning_score']['gate'] == 'pending'
    assert score_review(manifest, review)['meaning_score']['gate'] == 'pending'

