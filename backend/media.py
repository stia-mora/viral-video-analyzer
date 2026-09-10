import json
import math
import os
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from . import config


def run(args, timeout=180):
    completed = subprocess.run(
        [str(a) for a in args],
        capture_output=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        raise RuntimeError("媒体处理失败：" + completed.stderr[-800:])
    return completed.stdout


def atomic_media(args, target, timeout=180):
    temp = target.with_name(target.stem + ".pending" + target.suffix)
    try:
        run([*args, temp], timeout)
        if not temp.is_file() or temp.stat().st_size == 0:
            raise RuntimeError("媒体处理未产生有效文件")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def prepare_media(folder):
    candidates = [
        p
        for p in folder.glob("video.*")
        if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")
    ]
    if not candidates:
        raise RuntimeError("没有找到已下载的视频文件")
    video = max(candidates, key=lambda p: p.stat().st_size)
    info = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                video,
            ]
        )
    )
    duration = float(info["format"]["duration"])
    if (
        not math.isfinite(duration)
        or duration <= 0
        or duration > config.MAX_VIDEO_SECONDS
    ):
        raise ValueError("视频时长无效或超过 15 分钟限制")
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    playable = folder / "playback.mp4"
    if not playable.exists():
        if stream.get("codec_name") == "h264" and video.suffix == ".mp4":
            playable = video
        else:
            atomic_media(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    video,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                ],
                playable,
                600,
            )
    if not (folder / "cover.jpg").exists():
        atomic_media(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                video,
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
            ],
            folder / "cover.jpg",
        )
    # Normalize any webp/png response to an actual JPEG.
    with Image.open(folder / "cover.jpg") as image:
        image.convert("RGB").save(folder / "cover.jpg", quality=90)
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    if has_audio and not (folder / "audio.wav").exists():
        atomic_media(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                video,
                "-vn",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
            ],
            folder / "audio.wav",
        )
    frames = folder / "frames"
    frames.mkdir(exist_ok=True)
    interval = max(3, math.ceil(duration / 48))
    times = [float(t) for t in range(0, math.ceil(duration), interval)][:48]
    for index, second in enumerate(times):
        atomic_media(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                str(second),
                "-i",
                video,
                "-frames:v",
                "1",
                "-vf",
                "scale=512:-2",
            ],
            frames / f"frame-{index+1:03d}.jpg",
        )
    records, previous = [], None
    for index, second in enumerate(times):
        frame = frames / f"frame-{index+1:03d}.jpg"
        with Image.open(frame) as image:
            gray = image.convert("L").resize((64, 64))
            brightness = round(ImageStat.Stat(gray).mean[0] / 255 * 100, 1)
            delta = (
                round(
                    ImageStat.Stat(ImageChops.difference(gray, previous)).mean[0]
                    / 255
                    * 100,
                    1,
                )
                if previous
                else None
            )
            previous = gray.copy()
        records.append(
            {
                "time": round(second, 2),
                "file": "frames/" + frame.name,
                "brightness": brightness,
                "change": delta,
                "description": "",
                "method": "image_statistics",
            }
        )
    return {
        "duration": duration,
        "width": stream.get("width"),
        "height": stream.get("height"),
        "video_file": video.name,
        "playback_file": playable.name,
        "cover_file": "cover.jpg",
        "has_audio": has_audio,
        "frames": records,
        "frame_interval": interval,
    }


def transcript(folder, has_audio=True):
    if not has_audio:
        return {"text": "", "segments": [], "timing": "none", "note": "原视频无音轨"}
    plain = folder / "text_plain.txt"
    if not plain.exists() or not (folder / "asr_result.json").exists():
        executable = Path(config.ASR_PYTHON)
        if not executable.exists():
            raise RuntimeError(
                "本地 Qwen ASR 环境未安装，请按部署文档设置 PIANXI_ASR_PYTHON"
            )
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONNOUSERSITE"] = "1"
        # Cached local models should never stall on Hub metadata requests.
        local_models = []
        for model_name, flag in [
            ("Qwen3-ASR-1.7B", "--model"),
            ("Qwen3-ForcedAligner-0.6B", "--aligner"),
        ]:
            snapshots = (
                config.ROOT
                / ".hf-cache/hub"
                / ("models--Qwen--" + model_name)
                / "snapshots"
            )
            ready = [
                p
                for p in snapshots.glob("*")
                if (p / "config.json").exists() and any(p.glob("*.safetensors"))
            ]
            if ready:
                local_models.extend([flag, str(ready[0])])
        if len(local_models) == 4:
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
        staging = folder / "asr-pending"
        staging.mkdir(exist_ok=True)
        proc = subprocess.run(
            [
                str(executable),
                str(config.ROOT / "scripts/qwen3_asr_transcribe.py"),
                "--audio",
                str(folder / "audio.wav"),
                "--out-dir",
                str(staging),
                "--timestamps",
                "auto",
                *local_models,
            ],
            env=env,
            capture_output=True,
            timeout=1200,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        (folder / "asr.log").write_bytes(proc.stdout + b"\n" + proc.stderr)
        if proc.returncode:
            raise RuntimeError(
                "本地语音转写失败，请检查 GPU 和 Qwen 模型，或在文案页手动补充逐字稿"
            )
        for name in ["text_plain.txt", "text.txt", "asr_result.json"]:
            (staging / name).replace(folder / name)
    text = plain.read_text(encoding="utf-8").strip()
    lines = (
        (folder / "text.txt").read_text(encoding="utf-8")
        if (folder / "text.txt").exists()
        else ""
    )
    segments = [
        {"start": float(a), "end": float(b), "text": t.strip()}
        for a, b, t in re.findall(r"\[([\d.]+)s\s*->\s*([\d.]+)s\]\s*([^\n]+)", lines)
    ]
    meta = (
        json.loads((folder / "asr_result.json").read_text(encoding="utf-8"))
        if (folder / "asr_result.json").exists()
        else {}
    )
    timed = bool(meta.get("timestamps"))
    # Existing SRTs can supply a better alignment than legacy one-line transcript.
    if not timed and (folder / "subtitles.srt").exists():
        source = (folder / "subtitles.srt").read_text(encoding="utf-8-sig")

        def seconds(t):
            h, m, s = t.replace(",", ".").split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)

        rows = re.findall(
            r"(\d{2}:\d{2}:\d{2}[,.]\d+) --> (\d{2}:\d{2}:\d{2}[,.]\d+)\s*\n(.*?)(?=\n\s*\n|$)",
            source,
            re.S,
        )
        if rows:
            segments = [
                {"start": seconds(a), "end": seconds(b), "text": t.replace("\n", " ")}
                for a, b, t in rows
            ]
            timed = True
    return {
        "text": text,
        "segments": segments,
        "timing": "aligned" if timed else "whole_video",
        "note": (
            "本地 Qwen3-ASR 转写；请核对专有名词"
            if timed
            else "转写未对齐到句子，不能据此断言某句出现的秒数"
        ),
    }
