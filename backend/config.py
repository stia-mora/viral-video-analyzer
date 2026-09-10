import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("PIANXI_DATA", ROOT / "data")).resolve()
MEDIA = DATA / "media"
DB = DATA / "platform.sqlite3"
ASR_PYTHON = os.environ.get(
    "PIANXI_ASR_PYTHON", str(Path.home() / ".conda/envs/douyin-qwen-asr/python.exe")
)
MAX_VIDEO_SECONDS = 900
MAX_BYTES = 500 * 1024 * 1024


def prepare():
    MEDIA.mkdir(parents=True, exist_ok=True)
