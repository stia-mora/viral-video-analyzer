import json
import sys
from pathlib import Path


def srt_time(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: write_english_srt.py META_JSON OUTPUT_SRT")

    meta_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    entries = []
    for scene in meta["scenes"]:
        for line in scene["lines"]:
            entries.append(line)

    chunks = []
    for index, line in enumerate(entries, start=1):
        text = f"{line['role']}: {line['text']}"
        chunks.append(
            f"{index}\n{srt_time(line['start'])} --> {srt_time(line['end'])}\n{text}\n"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(chunks), encoding="utf-8")
    print(f"wrote {len(entries)} cues to {output_path}")


if __name__ == "__main__":
    main()
