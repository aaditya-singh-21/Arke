"""Local evaluation scaffolding; draft references are never asserted to be reviewed."""
from pathlib import Path
import hashlib
import json
import re
import unicodedata
import numpy as np
from .errors import InvalidInput

# Authored draft prompts. Hindi references require bilingual approval.
DRAFTS = [
    ("Hello, how are you today?", "नमस्ते, आज आप कैसे हैं?", ["clean", "conversation"]),
    ("Please speak a little more slowly.", "कृपया थोड़ा धीरे बोलिए।", ["clean", "conversation"]),
    ("Can you help me find the station?", "क्या आप स्टेशन खोजने में मेरी मदद कर सकते हैं?", ["clean", "question"]),
    ("I would like a glass of water.", "मुझे एक गिलास पानी चाहिए।", ["clean", "conversation"]),
    ("Thank you for waiting for me.", "मेरा इंतज़ार करने के लिए धन्यवाद।", ["clean", "conversation"]),
    ("The meeting starts at nine tomorrow.", "बैठक कल नौ बजे शुरू होगी।", ["clean", "numbers", "dates"]),
    ("Please call Aaditya after lunch.", "कृपया दोपहर के खाने के बाद आदित्य को फोन कीजिए।", ["clean", "names"]),
    ("Priya is travelling to Bengaluru today.", "प्रिया आज बेंगलुरु जा रही है।", ["clean", "names"]),
    ("The train leaves from platform twelve.", "ट्रेन बारह नंबर प्लेटफॉर्म से रवाना होगी।", ["clean", "numbers"]),
    ("Your order costs two hundred rupees.", "आपके ऑर्डर की कीमत दो सौ रुपये है।", ["clean", "numbers"]),
    ("I do not want sugar in my tea.", "मुझे अपनी चाय में चीनी नहीं चाहिए।", ["clean", "negation"]),
    ("Do not send this message yet.", "यह संदेश अभी मत भेजिए।", ["clean", "negation"]),
    ("The appointment is on October fifteenth.", "मुलाकात पंद्रह अक्टूबर को है।", ["clean", "dates"]),
    ("We need three tickets for Friday.", "हमें शुक्रवार के लिए तीन टिकट चाहिए।", ["clean", "numbers", "dates"]),
    ("Is the shop open on Sunday?", "क्या दुकान रविवार को खुली रहती है?", ["clean", "question", "dates"]),
    ("Could you please repeat that sentence?", "क्या आप कृपया वह वाक्य दोहरा सकते हैं?", ["clean", "indian_english", "question"]),
    ("I will reach the office in ten minutes.", "मैं दस मिनट में कार्यालय पहुँच जाऊँगा।", ["clean", "indian_english", "numbers"]),
    ("Please check the address before leaving.", "कृपया निकलने से पहले पता जाँच लीजिए।", ["clean", "indian_english"]),
    ("Rahul has not received the payment.", "राहुल को भुगतान नहीं मिला है।", ["clean", "indian_english", "names", "negation"]),
    ("There are twenty five people in the room.", "कमरे में पच्चीस लोग हैं।", ["clean", "indian_english", "numbers"]),
    ("The bus is running late today.", "बस आज देर से चल रही है।", ["noise", "conversation"]),
    ("Where can I buy a phone charger?", "मैं फोन का चार्जर कहाँ खरीद सकता हूँ?", ["noise", "question"]),
    ("Please close the window near you.", "कृपया अपने पास की खिड़की बंद कर दीजिए।", ["noise", "conversation"]),
    ("I cannot hear you clearly.", "मुझे आपकी आवाज़ साफ़ सुनाई नहीं दे रही है।", ["noise", "negation"]),
    ("Ananya will arrive at six thirty.", "अनन्या साढ़े छह बजे आएगी।", ["noise", "names", "numbers"]),
    ("Good morning, everyone.", "सभी को सुप्रभात।", ["clean", "short"]),
    ("Please wait a moment.", "कृपया एक क्षण रुकिए।", ["clean", "short"]),
    ("That is not correct.", "वह सही नहीं है।", ["clean", "short", "negation"]),
    ("Turn left after the bridge.", "पुल के बाद बाएँ मुड़िए।", ["clean", "conversation"]),
    ("My booking number is four seven two nine.", "मेरी बुकिंग संख्या चार सात दो नौ है।", ["clean", "numbers"]),
]


def init_evaluation(manifest: Path, synthetic=False):
    review = manifest.with_name("review-template.jsonl")
    if manifest.exists() or review.exists():
        raise InvalidInput("Evaluation manifest or review template already exists; refusing to overwrite references")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    cases = []
    for i, (english, hindi, tags) in enumerate(DRAFTS, 1):
        case_id = f"case-{i:02d}"
        duration = float(2 + (i - 1) % 5) if synthetic else None
        row = {"case_id": case_id, "audio_path": f"audio/{case_id}.wav", "source_duration": duration,
               "english_reference": english, "hindi_reference": hindi, "tags": tags,
               "english_reviewed": False, "hindi_reviewed": False,
               "audio_kind": "synthetic_tone" if synthetic else "human_recording_pending"}
        if synthetic:
            from .audio.normalize import write_wav
            from .types import AudioBuffer
            samples = (.1 * np.sin(2 * np.pi * 220 * np.arange(int(duration * 16000)) / 16000)).astype(np.float32)
            write_wav(manifest.parent / row["audio_path"], AudioBuffer(samples, 16000))
        cases.append(row)
    manifest.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in cases), encoding="utf-8")
    review.write_text("".join(json.dumps({"case_id": x["case_id"], "reviewer": "", "meaning_score": None,
        "tts_intelligibility_score": None, "critical_details_reviewed": False, "critical_detail_errors": [],
        "notes": "", "translation_run_id": "", "tts_run_id": ""}, ensure_ascii=False) + "\n" for x in cases), encoding="utf-8")
    return {"manifest": str(manifest), "cases": 30, "references_reviewed": False, "synthetic": synthetic,
            "human_steps": "Record 2-6 s WAVs; verify English; review Hindi; score generated speech and critical details"}


def read_jsonl(path):
    try:
        rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        if not all(isinstance(x, dict) for x in rows):
            raise ValueError()
        return rows
    except (OSError, ValueError) as exc:
        raise InvalidInput(f"Invalid JSONL file: {Path(path).name}") from exc


def load_manifest(path: Path, stage: str, allow_unreviewed=False):
    import soundfile as sf
    rows = read_jsonl(path)
    if len(rows) != 30:
        raise InvalidInput("The fixed evaluation set requires exactly 30 ordinary cases")
    ids = set()
    for index, row in enumerate(rows):
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", case_id) or case_id in ids:
            raise InvalidInput("Case IDs must be unique safe names")
        ids.add(case_id)
        if not isinstance(row.get("tags"), list) or not row["tags"] or not all(isinstance(x, str) for x in row["tags"]):
            raise InvalidInput(f"{case_id}: category tags required")
        for field in ("english_reference", "hindi_reference"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise InvalidInput(f"{case_id}: nonempty {field} required")
        if not allow_unreviewed and (row.get("english_reviewed") is not True or row.get("hindi_reviewed") is not True):
            raise InvalidInput(f"{case_id}: human-reviewed references required; --allow-unreviewed marks a diagnostic run")
        if row.get("audio_kind") != "human_recording" and not allow_unreviewed:
            raise InvalidInput(f"{case_id}: human recordings required for acceptance evaluation")
        audio_path = (path.resolve().parent / row.get("audio_path", "")).resolve()
        row = row.copy()
        row["resolved_audio_path"] = audio_path
        if stage in ("asr", "pipeline"):
            try:
                info = sf.info(audio_path)
            except (OSError, RuntimeError) as exc:
                raise InvalidInput(f"{case_id}: recording is missing or invalid") from exc
            actual = info.frames / info.samplerate
            stated = row.get("source_duration")
            if not isinstance(stated, (int, float)) or not 2 <= actual <= 6 or abs(actual - stated) > .02:
                raise InvalidInput(f"{case_id}: record and verify a 2-6 s duration")
        row["resolved_audio_path"] = audio_path
        # Replace the input row with a copy, never write reviewed data back implicitly.
        rows[index] = row
    return rows


def word_errors(reference: str, hypothesis: str):
    def words(text):
        text = unicodedata.normalize("NFKC", text).casefold()
        text = "".join(c if c.isalnum() or c.isspace() or c == "'" else " " for c in text)
        return text.split()
    ref, hyp = words(reference), words(hypothesis)
    previous = list(range(len(hyp) + 1))
    for i, a in enumerate(ref, 1):
        current = [i]
        for j, b in enumerate(hyp, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (a != b)))
        previous = current
    return {"errors": previous[-1], "reference_words": len(ref),
            "wer": previous[-1] / len(ref) if ref else None}


def score_review(manifest, review, translation_report=None, tts_report=None):
    cases = read_jsonl(manifest)
    rows = read_jsonl(review)
    ids = {x["case_id"] for x in cases}
    if len(cases) != 30 or len(ids) != 30 or len(rows) != 30 or {x.get("case_id") for x in rows} != ids:
        raise InvalidInput("Review must cover all 30 cases exactly once")
    complete = all(x.get("english_reviewed") is True and x.get("hindi_reviewed") is True
                   and x.get("audio_kind") == "human_recording" for x in cases)
    run_ids = {}
    for field, report_path, stages in (("translation_run_id", translation_report, ("translation", "pipeline")),
                                      ("tts_run_id", tts_report, ("tts",))):
        runs = {x.get(field) for x in rows}
        run_id = next(iter(runs)) if len(runs) == 1 else None
        run_ids[field] = run_id
        complete = complete and bool(run_id)
        if report_path is None:
            complete = False
            continue
        try:
            summary = json.loads(Path(report_path).read_text(encoding="utf-8"))
            metadata = json.loads(Path(report_path).with_name("metadata.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise InvalidInput("Review benchmark report/metadata is missing or invalid") from exc
        if summary.get("run_id") != run_id or metadata.get("run_id") != run_id:
            raise InvalidInput("Review run IDs do not match supplied benchmark evidence")
        if metadata.get("manifest_sha256") != hashlib.sha256(Path(manifest).read_bytes()).hexdigest():
            raise InvalidInput("References changed since benchmark; rerun against the reviewed fixed set")
        if metadata.get("stage") not in stages:
            raise InvalidInput("Review evidence must use translation/composed text and independent reviewed-input TTS")
        complete = complete and summary.get("fake") is False and summary.get("diagnostic_unreviewed") is False
        complete = complete and summary.get("measured", {}).get("successful") == 90 and summary.get("distinct_case_count") == 30
    for row in rows:
        for field in ("meaning_score", "tts_intelligibility_score"):
            value = row.get(field)
            if value is not None and (type(value) is not int or not 1 <= value <= 5):
                raise InvalidInput(f"Review {field} must be an integer from 1 to 5 or null")
        if not isinstance(row.get("critical_detail_errors"), list):
            raise InvalidInput("critical_detail_errors must be a list")
        complete = complete and bool(row.get("reviewer")) and row.get("critical_details_reviewed") is True
        complete = complete and all(row.get(f) is not None for f in ("meaning_score", "tts_intelligibility_score"))
    report = {"status": "reviewed" if complete else "human_review_pending", "cases": 30,
              "run_ids": run_ids,
              "critical_detail_errors": [{"case_id": x["case_id"], "errors": x["critical_detail_errors"]}
                                         for x in rows if x["critical_detail_errors"]]}
    for field in ("meaning_score", "tts_intelligibility_score"):
        scores = [x[field] for x in rows if x.get(field) is not None]
        report[field] = {"reviewed_count": len(scores), "fraction_at_least_4": sum(x >= 4 for x in scores) / 30,
                        "gate": ("pass" if sum(x >= 4 for x in scores) >= 27 else "fail") if complete else "pending"}
    return report

