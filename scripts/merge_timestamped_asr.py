from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TIMESTAMP_RE = re.compile(
    r"^\[(?P<start>\d+(?:\.\d+)?)s\s*->\s*(?P<end>\d+(?:\.\d+)?)s\]\s*(?P<text>.*)$"
)


def shift_line(line: str, offset: float) -> str:
    match = TIMESTAMP_RE.match(line.strip())
    if not match:
        return line.strip()
    start = float(match.group("start")) + offset
    end = float(match.group("end")) + offset
    return f"[{start:.1f}s -> {end:.1f}s] {match.group('text').strip()}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge a timestamped ASR tail into a base transcript.")
    parser.add_argument("--root", required=True, help="Final output directory containing the base ASR files.")
    parser.add_argument("--tail-dir", required=True, help="Directory containing the tail text files.")
    parser.add_argument("--offset", type=float, required=True, help="Tail start offset in seconds.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    tail_dir = Path(args.tail_dir).resolve()

    base_lines = [line.strip() for line in (root / "text.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    tail_lines = [line.strip() for line in (tail_dir / "text.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    merged_lines = base_lines + [shift_line(line, args.offset) for line in tail_lines]
    (root / "text.txt").write_text("\n".join(merged_lines) + "\n", encoding="utf-8")

    base_plain = (root / "text_plain.txt").read_text(encoding="utf-8").strip()
    tail_plain = (tail_dir / "text_plain.txt").read_text(encoding="utf-8").strip()
    (root / "text_plain.txt").write_text(f"{base_plain} {tail_plain}\n", encoding="utf-8")

    result_path = root / "asr_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["text"] = (root / "text_plain.txt").read_text(encoding="utf-8").strip()
    result["tail_recovery"] = {
        "offset_seconds": args.offset,
        "source": "segment_retranscription",
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
