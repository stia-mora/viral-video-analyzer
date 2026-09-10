"""Run with the configured VLM Python environment on a new machine."""

from pathlib import Path
from huggingface_hub import snapshot_download

root = Path(__file__).resolve().parents[1]
snapshot_download(
    "Qwen/Qwen3-VL-2B-Instruct",
    local_dir=str(root / ".hf-cache/vision-model"),
    ignore_patterns=["*.md", ".gitattributes"],
    max_workers=4,
)
