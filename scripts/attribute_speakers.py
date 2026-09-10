from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import torch
from qwen_asr import Qwen3ASRModel


DEFAULT_ASR_MODEL = "Qwen/Qwen3-ASR-1.7B"
DEFAULT_ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"

# Scene boundaries read from the burned-in role labels in the source video.
SEGMENTS = [
    (0.133, 3.667, "美国网友"),
    (3.667, 6.100, "中国网友"),
    (6.100, 9.833, "美国网友"),
    (9.833, 11.133, "中国网友"),
    (11.133, 13.500, "沙特网友"),
    (13.500, 16.333, "中国网友"),
    (16.333, 18.467, "美国网友"),
    (18.467, 23.400, "中国网友"),
    (23.400, 28.933, "美国网友"),
    (28.933, 32.600, "土耳其网友"),
    (32.600, 35.000, "日本网友"),
    (35.000, 42.033, "俄罗斯网友"),
    (42.033, 53.467, "沙特网友"),
    (53.467, 56.800, "美国网友"),
    (56.800, 57.567, "沙特网友"),
    (57.567, 63.600, "美国网友"),
    (63.600, 65.500, "沙特网友"),
    (65.500, 69.533, "美国网友"),
    (69.533, 75.233, "中国网友"),
    (75.233, 97.600, "沙特网友"),
    (97.600, 107.100, "中国网友"),
    (107.100, 112.167, "沙特网友"),
    (112.167, 127.600, "中国网友"),
    (127.600, 136.700, "美国网友"),
    (136.700, 144.667, "沙特网友"),
    (144.667, 150.433, "中国网友"),
    (150.433, 155.234, "中国网友"),
]


def configure_cache() -> None:
    project_root = Path(__file__).resolve().parents[1]
    cache = project_root / ".hf-cache"
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache / "hub"))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def srt_time(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds_value, millis_value = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_value:02d},{millis_value:03d}"


def group_timestamps(items: Any, max_chars: int = 24) -> list[tuple[float, float, str]]:
    entries: list[tuple[float, float, str]] = []
    buffer: list[str] = []
    start: float | None = None
    end: float | None = None
    hard_breaks = set("。！？!?；;\n")

    for item in items or []:
        text = str(getattr(item, "text", "") or "")
        if not text:
            continue
        item_start = float(getattr(item, "start_time", 0.0) or 0.0)
        item_end = float(getattr(item, "end_time", item_start) or item_start)
        if start is None:
            start = item_start
        end = item_end
        buffer.append(text)
        joined = "".join(buffer).strip()
        if joined and (joined[-1] in hard_breaks or len(joined) >= max_chars):
            entries.append((start, end or start, joined))
            buffer = []
            start = None
            end = None

    if buffer and start is not None:
        joined = "".join(buffer).strip()
        if joined:
            entries.append((start, end or start, joined))
    return entries


def extract_clips(video: Path, directory: Path) -> list[Path]:
    paths: list[Path] = []
    for index, (start, end, _role) in enumerate(SEGMENTS, 1):
        path = directory / f"part_{index:02d}.wav"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(start), "-to", str(end), "-i", str(video),
                "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(path),
            ],
            check=True,
        )
        paths.append(path)
    return paths


def transcribe_segments(paths: list[Path], batch_size: int) -> list[Any]:
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    model = Qwen3ASRModel.from_pretrained(
        DEFAULT_ASR_MODEL,
        dtype=dtype,
        device_map=device,
        max_inference_batch_size=batch_size,
        max_new_tokens=4096,
        forced_aligner=DEFAULT_ALIGNER_MODEL,
        forced_aligner_kwargs={"dtype": dtype, "device_map": device},
    )
    return model.transcribe(
        audio=[str(path) for path in paths],
        language=["Chinese"] * len(paths),
        return_time_stamps=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Attribute dialogue to the role shown in each video cut.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    configure_cache()
    video = Path(args.video).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="speaker_clips_") as temp_dir:
        clip_paths = extract_clips(video, Path(temp_dir))
        results = transcribe_segments(clip_paths, args.batch_size)

    records: list[dict[str, Any]] = []
    cue_index = 1
    srt_blocks: list[str] = []
    txt_lines: list[str] = []

    for index, ((segment_start, segment_end, role), result) in enumerate(zip(SEGMENTS, results), 1):
        entries = group_timestamps(result.time_stamps)
        if not entries and result.text:
            entries = [(0.0, segment_end - segment_start, result.text.strip())]

        segment_record = {
            "index": index,
            "start": segment_start,
            "end": segment_end,
            "role": role,
            "text": (result.text or "").strip(),
            "cues": [],
        }
        for relative_start, relative_end, text in entries:
            start = segment_start + relative_start
            end = min(segment_end, segment_start + relative_end)
            segment_record["cues"].append({"start": start, "end": end, "text": text})
            txt_lines.append(f"[{srt_time(start)} --> {srt_time(end)}] {role}：{text}")
            srt_blocks.append(f"{cue_index}\n{srt_time(start)} --> {srt_time(end)}\n[{role}] {text}")
            cue_index += 1
        records.append(segment_record)

    (out_dir / "speaker_transcript.txt").write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    (out_dir / "speaker_transcript.srt").write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")
    (out_dir / "speaker_transcript.json").write_text(
        json.dumps({"video": str(video), "segments": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"segments={len(records)} cues={cue_index - 1}")
    print(f"wrote={out_dir / 'speaker_transcript.txt'}")
    print(f"wrote={out_dir / 'speaker_transcript.srt'}")
    print(f"wrote={out_dir / 'speaker_transcript.json'}")


if __name__ == "__main__":
    main()
