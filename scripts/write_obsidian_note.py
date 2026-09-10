from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a Douyin transcript note into an Obsidian vault root.")
    parser.add_argument("--out-dir", required=True, help="Directory containing video.info.json, text_plain.txt, and text.txt.")
    parser.add_argument("--vault", required=True, help="Obsidian vault root. The note is written directly here.")
    parser.add_argument("--filename", default=None, help="Optional output filename without or with .md.")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def strip_hashtags(title: str) -> str:
    title = re.sub(r"\s*#\S+", "", title).strip()
    return title or "抖音视频转写"


def safe_filename(name: str, limit: int = 80) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:limit].strip() or "抖音视频转写") + ".md"


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir).resolve()
    vault = Path(args.vault).resolve()
    vault.mkdir(parents=True, exist_ok=True)

    info = read_json(out_dir / "video.info.json")
    asr = read_json(out_dir / "asr_result.json")
    plain = (out_dir / "text_plain.txt").read_text(encoding="utf-8").strip()
    timed = (out_dir / "text.txt").read_text(encoding="utf-8").strip()

    raw_title = info.get("title") or info.get("fulltitle") or "抖音视频转写"
    note_title = strip_hashtags(raw_title)
    filename = args.filename if args.filename else safe_filename(note_title)
    if not filename.lower().endswith(".md"):
        filename += ".md"

    url = info.get("webpage_url") or info.get("original_url") or ""
    author = info.get("channel") or info.get("uploader") or ""
    upload_date = info.get("upload_date") or ""
    duration = info.get("duration") or asr.get("duration_seconds") or ""
    asr_model = asr.get("model") or "Qwen/Qwen3-ASR-1.7B"
    aligner = asr.get("aligner") or ""

    note = f"""---
source: 抖音
url: {url}
author: {author}
date: {upload_date}
duration: {duration}s
asr_model: {asr_model}
forced_aligner: {aligner}
tags: [抖音转录, Qwen3-ASR, 知识库]
---

# {note_title}

**原视频标题：** {raw_title}  
**来源：** [抖音]({url})  
**作者：** {author}  
**时长：** {duration}s  
**ASR：** {asr_model}

## 文字稿

{plain}

## 带时间戳转写

```text
{timed}
```
"""

    dest = vault / filename
    dest.write_text(note, encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
