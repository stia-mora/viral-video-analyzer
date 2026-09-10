from __future__ import annotations

import argparse
import json
import os
import wave
from pathlib import Path
from typing import Optional

import torch
from qwen_asr import Qwen3ASRModel
from asr_utils import group_timestamp_items

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASR_MODEL = "Qwen/Qwen3-ASR-1.7B"
DEFAULT_ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe audio with Qwen3-ASR-1.7B."
    )
    parser.add_argument(
        "--audio",
        required=True,
        help="Path to input audio, preferably 16 kHz mono WAV.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory for text.txt, text_plain.txt, and asr_result.json.",
    )
    parser.add_argument(
        "--model", default=DEFAULT_ASR_MODEL, help="Qwen3-ASR model name or local path."
    )
    parser.add_argument(
        "--aligner",
        default=DEFAULT_ALIGNER_MODEL,
        help="Forced aligner model name or local path.",
    )
    parser.add_argument(
        "--language",
        default="Chinese",
        help="Qwen language label, e.g. Chinese, English, or auto.",
    )
    parser.add_argument(
        "--timestamps", choices=("auto", "always", "off"), default="auto"
    )
    parser.add_argument("--max-new-tokens", type=int, default=4096)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--cpu", action="store_true", help="Force CPU inference.")
    return parser.parse_args()


def configure_cache() -> None:
    cache = PROJECT_ROOT / ".hf-cache"
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache / "hub"))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def wav_duration_seconds(path: Path) -> Optional[float]:
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return None


def choose_runtime(force_cpu: bool) -> tuple[str, torch.dtype]:
    if not force_cpu and torch.cuda.is_available():
        return "cuda:0", torch.bfloat16
    return "cpu", torch.float32


def should_use_timestamps(mode: str, duration: Optional[float]) -> bool:
    if mode == "off":
        return False
    if mode == "always":
        return True
    # Qwen3-ForcedAligner is documented for up to 5 minutes of speech.
    return duration is not None and duration <= 300


def main() -> None:
    args = parse_args()
    configure_cache()

    audio = Path(args.audio).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    duration = wav_duration_seconds(audio)
    device_map, dtype = choose_runtime(args.cpu)
    language = None if args.language.lower() == "auto" else args.language
    use_timestamps = should_use_timestamps(args.timestamps, duration)

    print(f"audio={audio}")
    print(f"model={args.model}")
    print(f"device_map={device_map} dtype={dtype}")
    print(f"timestamps={use_timestamps} duration={duration}")

    model_kwargs = dict(
        dtype=dtype,
        device_map=device_map,
        max_inference_batch_size=args.batch_size,
        max_new_tokens=args.max_new_tokens,
    )
    if use_timestamps:
        model_kwargs["forced_aligner"] = args.aligner
        model_kwargs["forced_aligner_kwargs"] = dict(dtype=dtype, device_map=device_map)

    model = Qwen3ASRModel.from_pretrained(args.model, **model_kwargs)
    result = model.transcribe(
        audio=str(audio),
        language=language,
        return_time_stamps=use_timestamps,
    )[0]

    plain_text = (result.text or "").strip()
    (out_dir / "text_plain.txt").write_text(plain_text + "\n", encoding="utf-8")

    timestamp_lines: List[str]
    if use_timestamps and result.time_stamps:
        timestamp_lines = group_timestamp_items(
            result.time_stamps, language=result.language
        )
    else:
        end = duration if duration is not None else 0.0
        timestamp_lines = [f"[0.0s -> {end:.1f}s] {plain_text}"] if plain_text else []
    (out_dir / "text.txt").write_text(
        "\n".join(timestamp_lines) + "\n", encoding="utf-8"
    )

    payload = {
        "model": args.model,
        "aligner": args.aligner if use_timestamps else None,
        "language": result.language,
        "requested_language": args.language,
        "duration_seconds": duration,
        "device_map": device_map,
        "dtype": str(dtype),
        "timestamps": use_timestamps,
        "text": plain_text,
    }
    (out_dir / "asr_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"language={result.language}")
    print(f"chars={len(plain_text)}")
    print(f"wrote={out_dir / 'text_plain.txt'}")
    print(f"wrote={out_dir / 'text.txt'}")
    print(f"wrote={out_dir / 'asr_result.json'}")


if __name__ == "__main__":
    main()
