"""Local voiceover for the Grader Audit KT video (Kokoro, runs entirely on this machine).

Reads the approved narration from script.md, synthesizes it sentence by sentence, and writes:
  audio/scene_XX.wav     speech for each scene (24 kHz mono)
  audio/narration.wav    all scenes with SCENE_PAD seconds of silence after each one
  timing.json            scene/sentence boundaries and Kokoro word timestamps (global seconds)
  out/captions.srt       captions on the final timeline
  out/chapters.txt       chapter start times

Sentence audio is cached in audio/cache/ by (text, voice, speed, lang, library versions), so only
changed sentences are re-synthesized.

Usage: .venv/Scripts/python tts.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "script.md"
AUDIO = HERE / "audio"
CACHE = AUDIO / "cache"
OUT = HERE / "out"

VOICE = "af_heart"
LANG = "a"  # American English
SPEED = 1.0
SR = 24000
SENTENCE_GAP = 0.18  # silence between sentences within a scene
SCENE_PAD = 0.6  # silence after each scene
REPO_ID = "hexgrad/Kokoro-82M"

# Captions show what the screen shows, not the pronunciation spelling used for the voice.
CAPTION_SUBS = [
    ("Python, dash m, audit dot serve", "python -m audit.serve"),
    ("orders dot C S V", "orders.csv"), ("customer I D", "customer ID"),
    ("results dot json", "results.json"), ("Build tasks", "build_tasks"), ("Build probes", "build_probes"),
    ("Run audit", "run_audit"), ("grade k", "_grade_k"),
    ("A one", "A1"), ("A two", "A2"), ("T four", "T4"), ("S one", "S1"),
    ("One hundred fifty-two", "152"), ("one hundred thirty-nine", "139"), ("thirteen", "13"),
    ("five hundred seventy-four", "574"), ("five hundred seven", "507"), ("one hundred forty-three", "143"),
    ("one hundred forty-two", "142"), ("eighty-one", "81"), ("three hundred", "300"),
    ("twenty-six", "26"), ("seven", "7"), ("ninety-six", "96"), ("Forty-seven", "47"), ("forty-seven", "47"),
    ("forty-nine", "49"), ("twenty", "20"), ("fourteen", "14"), ("seventeen", "17"), ("twelve", "12"),
]


def settings() -> dict:
    return {"voice": VOICE, "lang_code": LANG, "speed": SPEED, "sample_rate": SR, "repo_id": REPO_ID,
            "sentence_gap": SENTENCE_GAP, "scene_pad": SCENE_PAD,
            "kokoro": version("kokoro"), "misaki": version("misaki")}


def load_scenes() -> list[dict]:
    text = SCRIPT.read_text(encoding="utf-8")
    scenes = []
    for m in re.finditer(r"^## Scene (\d+): (.+)$", text, flags=re.M):
        body = text[m.end():]
        nxt = re.search(r"^## ", body, flags=re.M)
        body = body[: nxt.start()] if nxt else body
        narr = re.search(r"\*\*Narration\*\*\s*\n\s*\n((?:> .*\n?)+)", body)
        if not narr:
            sys.exit(f"Scene {m.group(1)} has no Narration block")
        spoken = " ".join(line[2:].strip() for line in narr.group(1).splitlines())
        scenes.append({"n": int(m.group(1)), "title": m.group(2).strip(), "text": spoken})
    return scenes


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if s.strip()]


_pipeline = None


def synth(sentence: str, cfg: dict) -> tuple[np.ndarray, list]:
    key = hashlib.sha256(json.dumps({"text": sentence, **cfg}, sort_keys=True).encode()).hexdigest()[:24]
    wav, words = CACHE / f"{key}.wav", CACHE / f"{key}.json"
    if wav.exists() and words.exists():
        audio, _ = sf.read(wav, dtype="float32")
        return audio, json.loads(words.read_text(encoding="utf-8"))

    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline
        _pipeline = KPipeline(lang_code=LANG, repo_id=REPO_ID)
    chunks, toks, offset = [], [], 0.0
    for r in _pipeline(sentence, voice=VOICE, speed=SPEED, split_pattern=None):
        a = r.audio.detach().cpu().numpy().astype("float32")
        for t in r.tokens or []:
            if t.start_ts is not None and t.end_ts is not None and re.search(r"\w", t.text):
                toks.append([t.text, round(offset + t.start_ts, 3), round(offset + t.end_ts, 3)])
        chunks.append(a)
        offset += len(a) / SR
    audio = np.concatenate(chunks)
    CACHE.mkdir(parents=True, exist_ok=True)
    sf.write(wav, audio, SR, subtype="FLOAT")
    words.write_text(json.dumps(toks), encoding="utf-8")
    print(f"  synthesized: {sentence[:60]}")
    return audio, toks


def caption_text(spoken: str) -> str:
    out = spoken
    for a, b in CAPTION_SUBS:
        out = re.sub(rf"\b{re.escape(a)}\b", b, out)
    return out


def wrap(text: str, width: int = 42) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + ([cur] if cur else [])


def balanced_groups(text: str, max_lines: int = 2, width: int = 42) -> list[str]:
    """Split text into the fewest cues of <= max_lines lines, with words spread evenly so no cue is
    a one-word orphan."""
    words = text.split()
    n = 1
    while True:
        target = len(text) / n
        groups, cur = [], []
        for w in words:
            if cur and len(" ".join(cur + [w])) > target and len(groups) < n - 1:
                groups.append(" ".join(cur))
                cur = [w]
            else:
                cur.append(w)
        groups.append(" ".join(cur))
        if all(len(wrap(g, width)) <= max_lines for g in groups):
            return groups
        n += 1


def cues_for_sentence(text: str, start: float, end: float) -> list[tuple[float, float, str]]:
    """Split a caption sentence into <=2-line cues. Sub-sentence timing is proportional to
    character count (an estimate); sentence boundaries come from the measured audio."""
    groups = balanced_groups(text)
    total = sum(len(g) for g in groups)
    cues, t = [], start
    for g in groups:
        dur = (end - start) * len(g) / total
        cues.append((t, t + dur, "\n".join(wrap(g))))
        t += dur
    return cues


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> None:
    cfg = settings()
    scenes = load_scenes()
    AUDIO.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    gap = np.zeros(int(round(SENTENCE_GAP * SR)), dtype="float32")
    pad = np.zeros(int(round(SCENE_PAD * SR)), dtype="float32")

    timeline, full, t0 = [], [], 0.0
    for sc in scenes:
        parts, sentences, words, cursor = [], [], [], 0
        for i, sent in enumerate(split_sentences(sc["text"])):
            if i:
                parts.append(gap)
                cursor += len(gap)
            audio, toks = synth(sent, cfg)
            s0 = t0 + cursor / SR
            sentences.append({"text": sent, "start": round(s0, 3), "end": round(s0 + len(audio) / SR, 3)})
            words += [[w, round(s0 + a, 3), round(s0 + b, 3)] for w, a, b in toks]
            parts.append(audio)
            cursor += len(audio)
        speech = np.concatenate(parts)
        sf.write(AUDIO / f"scene_{sc['n']:02d}.wav", speech, SR, subtype="PCM_16")
        speech_dur = len(speech) / SR
        timeline.append({"n": sc["n"], "title": sc["title"], "start": round(t0, 3),
                         "speech": round(speech_dur, 3), "end": round(t0 + speech_dur + SCENE_PAD, 3),
                         "sentences": sentences, "words": words})
        full += [speech, pad]
        t0 += speech_dur + SCENE_PAD

    narration = np.concatenate(full)
    sf.write(AUDIO / "narration.wav", narration, SR, subtype="PCM_16")
    total = len(narration) / SR
    timing = {"settings": cfg, "total": round(total, 3),
              "word_timestamps": "Kokoro token start/end per sentence, offset to the global timeline",
              "scenes": timeline}
    (HERE / "timing.json").write_text(json.dumps(timing, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    cues = []
    for sc in timeline:
        for s in sc["sentences"]:
            cues += cues_for_sentence(caption_text(s["text"]), s["start"], s["end"])
    srt = "\n".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(cues, 1))
    (OUT / "captions.srt").write_text(srt, encoding="utf-8")

    chapters = "\n".join(f"{int(sc['start'] // 60):02d}:{int(sc['start'] % 60):02d} {sc['title']}" for sc in timeline)
    (OUT / "chapters.txt").write_text(chapters + "\n", encoding="utf-8")

    for sc in timeline:
        print(f"scene {sc['n']:2d}  start {sc['start']:7.2f}s  speech {sc['speech']:6.2f}s  {sc['title']}")
    print(f"total {total:.2f}s ({total / 60:.2f} min), {len(cues)} caption cues")


if __name__ == "__main__":
    main()
